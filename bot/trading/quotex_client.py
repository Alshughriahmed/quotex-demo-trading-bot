from __future__ import annotations

import asyncio
import inspect
import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import database


LOG_DIR = Path(__file__).resolve().parents[1] / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger("quotex")
if not logger.handlers:
    logger.setLevel(logging.INFO)
    handler = logging.FileHandler(LOG_DIR / "quotex.log", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    logger.propagate = False


class QuotexClientError(RuntimeError):
    """Base error for Quotex client failures."""


class QuotexDependencyError(QuotexClientError):
    """Raised when pyquotex is not installed or cannot be imported."""


class QuotexCredentialsError(QuotexClientError):
    """Raised when Quotex account credentials are missing."""


class QuotexConnectionError(QuotexClientError):
    """Raised when Quotex connection fails."""


class QuotexAssetUnavailable(QuotexClientError):
    """Raised when an asset is not available on the connected Quotex account."""


@dataclass(slots=True)
class QuotexCredentials:
    email: str
    password: str
    account_type: str = "DEMO"


@dataclass(slots=True)
class QuotexStatus:
    connected: bool
    message: str
    account_type: str
    balance: float | None = None


def load_credentials(db_path: str) -> QuotexCredentials:
    account = database.get_quotex_account(db_path)
    if not account or not account["email"] or not account["password"]:
        raise QuotexCredentialsError("Quotex account email/password are missing.")

    return QuotexCredentials(
        email=account["email"],
        password=account["password"],
        account_type=account["account_type"] or "DEMO",
    )


def _import_pyquotex():
    try:
        from pyquotex.stable_api import Quotex
    except Exception as exc:  # pragma: no cover - depends on server package state
        raise QuotexDependencyError(
            "pyquotex is not installed. Install it with: "
            "pip install git+https://github.com/cleitonleonel/pyquotex.git"
        ) from exc
    return Quotex


async def _maybe_await(value):
    if inspect.isawaitable(value):
        return await value
    return value


class QuotexClient:
    """Small async wrapper around pyquotex.

    This module owns Quotex communication only. It does not send Telegram
    messages and does not decide trades.
    """

    def __init__(self, db_path: str, lang: str = "en", root_path: str | None = None):
        self.db_path = db_path
        self.lang = lang
        self.root_path = root_path or str(Path(__file__).resolve().parents[1] / ".quotex")
        self.client: Any | None = None
        self.credentials: QuotexCredentials | None = None
        self.asset_cache: dict[tuple[str, bool], tuple[str, float]] = {}
        self.unavailable_asset_cache: dict[tuple[str, bool], float] = {}
        self.asset_cache_ttl = 300.0

    async def reconnect(self, reason: str = "") -> QuotexStatus:
        logger.warning("Reconnecting to Quotex reason=%s", reason or "unspecified")
        await self.close()
        self.asset_cache.clear()
        self.unavailable_asset_cache.clear()
        return await self.connect()

    async def connect(self, retries: int = 3, retry_delay: float = 3.0) -> QuotexStatus:
        self.credentials = load_credentials(self.db_path)
        Quotex = _import_pyquotex()

        Path(self.root_path).mkdir(parents=True, exist_ok=True)
        logger.info("Connecting to Quotex email=%s account_type=%s", self.credentials.email, self.credentials.account_type)

        self.client = Quotex(
            email=self.credentials.email,
            password=self.credentials.password,
            lang=self.lang,
            root_path=self.root_path,
        )
        if hasattr(self.client, "debug_ws_enable"):
            self.client.debug_ws_enable = False

        last_message = ""
        for attempt in range(1, retries + 1):
            try:
                check_connect, message = await _maybe_await(self.client.connect())
                last_message = str(message)
                if check_connect:
                    await self.change_account(self.credentials.account_type)
                    balance = await self.get_balance()
                    logger.info("Quotex connected account_type=%s balance=%s", self.credentials.account_type, balance)
                    return QuotexStatus(True, "connected", self.credentials.account_type, balance)
                logger.warning("Quotex connect failed attempt=%s message=%s", attempt, message)
            except Exception as exc:
                last_message = str(exc)
                logger.exception("Quotex connect exception attempt=%s", attempt)

            if attempt < retries:
                await asyncio.sleep(retry_delay)

        raise QuotexConnectionError(f"Quotex connection failed: {last_message}")

    async def change_account(self, account_type: str | None = None) -> None:
        if not self.client:
            raise QuotexConnectionError("Quotex client is not connected.")

        account_type = (account_type or "DEMO").upper()
        mode = "PRACTICE" if account_type in {"DEMO", "PRACTICE"} else "REAL"

        if hasattr(self.client, "change_account"):
            await _maybe_await(self.client.change_account(mode))
        elif hasattr(self.client, "set_account_mode"):
            await _maybe_await(self.client.set_account_mode(mode))
        logger.info("Quotex account mode set to %s", mode)

    async def get_balance(self) -> float | None:
        if not self.client:
            raise QuotexConnectionError("Quotex client is not connected.")
        balance = await _maybe_await(self.client.get_balance())
        try:
            return float(balance)
        except (TypeError, ValueError):
            return None

    async def check_connect(self) -> bool:
        if not self.client:
            return False
        if hasattr(self.client, "check_connect"):
            return bool(await _maybe_await(self.client.check_connect()))
        return True

    async def get_candles(self, asset: str, period: int = 60, offset: int = 3600) -> list[dict[str, Any]]:
        if not self.client:
            raise QuotexConnectionError("Quotex client is not connected.")

        symbol = await self.resolve_asset(asset, force_open=True, require_available=True)
        if hasattr(self.client, "get_candles"):
            candles = await _maybe_await(self.client.get_candles(symbol, time.time(), offset, period))
            normalized = normalize_candles(candles)
            expected = max(1, int(offset / period)) if period else 1
            if normalized and len(normalized) >= min(60, expected):
                return normalized

        if hasattr(self.client, "get_candle_v2"):
            candles = await _maybe_await(self.client.get_candle_v2(symbol, period))
            normalized = normalize_candles(candles)
            expected = max(1, int(offset / period)) if period else 1
            if normalized and len(normalized) >= min(60, expected):
                return normalized

        if hasattr(self.client, "get_historical_candles"):
            candles = await _maybe_await(
                self.client.get_historical_candles(
                    symbol,
                    amount_of_seconds=offset,
                    period=period,
                    max_workers=2,
                )
            )
            return normalize_candles(candles)

        raise QuotexClientError("Installed pyquotex version does not expose candle methods.")

    async def get_latest_price(self, asset: str) -> float | None:
        candles = await self.get_candles(asset, period=60, offset=300)
        if not candles:
            return None
        last = candles[-1]
        for key in ("close", "price"):
            if key in last and last[key] is not None:
                try:
                    return float(last[key])
                except (TypeError, ValueError):
                    return None
        return None

    async def get_payout(self, asset: str, duration_seconds: int) -> float | None:
        if not self.client:
            raise QuotexConnectionError("Quotex client is not connected.")

        symbol = await self.resolve_asset(asset, force_open=True, require_available=True)
        timeframe = "5" if duration_seconds >= 300 else "1"

        if hasattr(self.client, "get_payout_by_asset"):
            payout = await _maybe_await(self.client.get_payout_by_asset(symbol, timeframe=timeframe))
            parsed = parse_number(payout)
            if parsed is not None:
                return parsed

        if hasattr(self.client, "get_payment"):
            payments = await _maybe_await(self.client.get_payment())
            if isinstance(payments, dict):
                data = payments.get(symbol) or payments.get(normalize_asset(symbol))
                if isinstance(data, dict):
                    profit = data.get("profit")
                    if isinstance(profit, dict):
                        parsed = parse_number(profit.get(f"{timeframe}M"))
                        if parsed is not None:
                            return parsed
                    for key in ("turbo_payment", "payment"):
                        parsed = parse_number(data.get(key))
                        if parsed is not None:
                            return parsed
        return None

    async def buy_demo(
        self,
        amount: float,
        asset: str,
        direction: str,
        duration: int,
        *,
        resolve: bool = True,
    ) -> tuple[bool, Any]:
        if not self.client or not self.credentials:
            raise QuotexConnectionError("Quotex client is not connected.")
        if self.credentials.account_type.upper() not in {"DEMO", "PRACTICE"}:
            raise QuotexClientError("Automatic buying is enabled for DEMO only.")
        if amount <= 0:
            raise QuotexClientError("Trade amount must be greater than 0.")

        symbol = (
            await self.resolve_asset(asset, force_open=True, require_available=True)
            if resolve
            else normalize_asset(asset)
        )
        order_direction = direction.lower()
        if order_direction not in {"call", "put"}:
            raise QuotexClientError(f"Unsupported direction: {direction}")

        logger.info("Placing DEMO order asset=%s direction=%s amount=%s duration=%s", symbol, order_direction, amount, duration)
        status, buy_info = await _maybe_await(
            self.client.buy(amount, symbol, order_direction, duration, time_mode="TIMER")
        )
        if status:
            logger.info("DEMO order confirmed asset=%s order_id=%s", symbol, extract_order_id(buy_info))
        else:
            logger.warning("DEMO order failed asset=%s response=%s", symbol, safe_json_dumps(buy_info))
        return bool(status), buy_info

    async def resolve_asset(self, asset: str, force_open: bool = True, require_available: bool = False) -> str:
        if not self.client:
            raise QuotexConnectionError("Quotex client is not connected.")

        symbol = normalize_asset(asset)
        cache_key = (symbol, force_open)
        now = time.monotonic()
        unavailable_at = self.unavailable_asset_cache.get(cache_key)
        if unavailable_at and now - unavailable_at <= self.asset_cache_ttl:
            if require_available:
                raise QuotexAssetUnavailable(f"Asset is not available on Quotex: {symbol}")
            return symbol

        cached = self.asset_cache.get(cache_key)
        if cached and now - cached[1] <= self.asset_cache_ttl:
            return cached[0]

        if hasattr(self.client, "get_available_asset"):
            try:
                resolved, data = await _maybe_await(self.client.get_available_asset(symbol, force_open=force_open))
                if resolved:
                    resolved_symbol = str(resolved)
                    self.asset_cache[cache_key] = (resolved_symbol, now)
                    self.asset_cache[(normalize_asset(resolved_symbol), force_open)] = (resolved_symbol, now)
                    self.unavailable_asset_cache.pop(cache_key, None)
                    logger.info("Resolved asset %s -> %s availability=%s", symbol, resolved, data)
                    return resolved_symbol
                self.unavailable_asset_cache[cache_key] = now
                logger.info("Asset unavailable asset=%s availability=%s", symbol, data)
                if require_available:
                    raise QuotexAssetUnavailable(f"Asset is not available on Quotex: {symbol}")
            except QuotexAssetUnavailable:
                raise
            except Exception:
                logger.exception("Failed to resolve asset=%s", symbol)
                if require_available:
                    raise QuotexAssetUnavailable(f"Could not verify Quotex asset availability: {symbol}")
        if require_available:
            raise QuotexAssetUnavailable(f"Asset is not available on Quotex: {symbol}")
        self.asset_cache[cache_key] = (symbol, now)
        return symbol

    async def check_order_result(self, order_id: str | int, duration: int) -> tuple[str, float]:
        if not self.client:
            raise QuotexConnectionError("Quotex client is not connected.")
        result, profit = await _maybe_await(self.client.check_win(order_id, duration))
        logger.info("DEMO order result order_id=%s result=%s profit=%s", order_id, result, profit)
        return str(result).lower(), float(profit or 0)

    async def close(self) -> None:
        if not self.client:
            return
        try:
            if hasattr(self.client, "close"):
                await _maybe_await(self.client.close())
                logger.info("Quotex connection closed.")
        finally:
            self.client = None

    async def __aenter__(self) -> "QuotexClient":
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        await self.close()


def normalize_asset(asset: str) -> str:
    symbol = asset.replace("/", "").replace(" ", "")
    if symbol.lower().endswith("_otc"):
        return f"{symbol[:-4].upper()}_otc"
    return symbol.upper()


def extract_order_id(buy_info: Any) -> str | None:
    if isinstance(buy_info, dict):
        for key in ("id", "order_id", "ticket", "option_id"):
            value = buy_info.get(key)
            if value is not None:
                return str(value)
        data = buy_info.get("data")
        if isinstance(data, dict):
            return extract_order_id(data)
    return None


def safe_json_dumps(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except TypeError:
        return str(value)


def parse_number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_candles(raw_candles) -> list[dict[str, Any]]:
    if not raw_candles:
        return []

    normalized = []
    for candle in raw_candles:
        if isinstance(candle, dict):
            normalized.append(candle)
            continue
        if isinstance(candle, (list, tuple)):
            normalized.append(
                {
                    "time": candle[0] if len(candle) > 0 else None,
                    "open": candle[1] if len(candle) > 1 else None,
                    "close": candle[2] if len(candle) > 2 else None,
                    "high": candle[3] if len(candle) > 3 else None,
                    "low": candle[4] if len(candle) > 4 else None,
                }
            )
    return normalized


async def test_login(db_path: str) -> QuotexStatus:
    client = QuotexClient(db_path)
    try:
        return await client.connect()
    finally:
        await client.close()
