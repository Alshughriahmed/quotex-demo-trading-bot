from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from aiogram import Bot

import database
import menu
from trading.quotex_client import QuotexAssetUnavailable, QuotexClient, extract_order_id, safe_json_dumps
from trading.strategy import NO_TRADE, StrategyDecision, analyze, get_profile


LOG_DIR = Path(__file__).resolve().parents[1] / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger("trader")
if not logger.handlers:
    logger.setLevel(logging.INFO)
    handler = logging.FileHandler(LOG_DIR / "trader.log", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    logger.propagate = False


AUTO_ENTRY_DEFAULT_OFFSET_MS = 150
AUTO_ENTRY_MAX_OFFSET_MS = 800
AUTO_ENTRY_TARGET_MIN_MS = 80
AUTO_ENTRY_TARGET_MAX_MS = 300
EMPTY_CANDLES_RECONNECT_LIMIT = 3


@dataclass(slots=True)
class TradeCandidate:
    decision: StrategyDecision
    asset_symbol: str
    quotex_symbol: str
    fixed_quotex_symbol: bool = False
    payout: float | None = None
    pre_entry_price: float | None = None


class TradingRunner:
    def __init__(self, bot: Bot, db_path: str):
        self.bot = bot
        self.db_path = db_path
        self.client = QuotexClient(db_path)
        self.client_lock = asyncio.Lock()
        self.stop_event = asyncio.Event()
        self.trade_tasks: set[asyncio.Task] = set()

    async def run(self) -> None:
        logger.info("Trading runner started.")
        while not self.stop_event.is_set():
            try:
                await self.tick()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Trading tick failed.")

            schedule = database.get_signal_schedule(self.db_path)
            await self.sleep(schedule["scan_interval_seconds"])

    async def stop(self) -> None:
        self.stop_event.set()
        for task in list(self.trade_tasks):
            task.cancel()
        await self.client.close()
        logger.info("Trading runner stopped.")

    async def tick(self) -> None:
        settings = database.get_settings(self.db_path)
        if settings.get("bot_enabled", "false").lower() != "true":
            return

        schedule = database.get_signal_schedule(self.db_path)
        if schedule["single_open_trade"] and database.get_active_trade(self.db_path):
            return

        now = datetime.now(timezone.utc)
        if not is_signal_window(now, schedule["scan_interval_seconds"]):
            return

        risk_message = self.check_risk(settings)
        if risk_message:
            logger.info("Risk blocked signal: %s", risk_message)
            return

        candidate = await self.find_best_candidate(settings)
        if not candidate or not candidate.decision.has_trade:
            return

        entry_time = next_entry_time(datetime.now(timezone.utc), min_notice_seconds=10)
        if not self.can_scan_by_schedule(entry_time, schedule):
            return

        await self.create_and_send_trade(candidate, settings, entry_time)

    def can_scan_by_schedule(self, entry_time: datetime, schedule: dict) -> bool:
        if schedule["mode"] == "open":
            return True

        last_trade_time = database.get_last_trade_time(self.db_path)
        if not last_trade_time:
            return True

        last_dt = parse_datetime(last_trade_time)
        elapsed = (entry_time - last_dt).total_seconds()
        target_window = max(0, int(schedule.get("signal_interval_seconds") or 0))
        allowed = elapsed >= target_window
        logger.info(
            "Signal timing window elapsed_seconds=%.0f target_window_seconds=%s allowed=%s",
            elapsed,
            target_window,
            allowed,
        )
        return allowed

    def check_risk(self, settings: dict) -> str | None:
        stats = database.get_today_stats(self.db_path)
        max_daily = safe_int(settings.get("max_daily_trades"), 0)
        if max_daily > 0 and stats["total"] >= max_daily:
            return "max_daily_trades"

        daily_loss_limit = safe_float(settings.get("daily_loss_limit"), 0)
        if daily_loss_limit > 0 and stats["profit_loss"] <= -daily_loss_limit:
            return "daily_loss_limit"

        stop_after_losses = safe_int(settings.get("stop_after_losses"), 0)
        if stop_after_losses > 0 and database.count_consecutive_losses(self.db_path) >= stop_after_losses:
            return "stop_after_losses"

        return None

    async def find_best_candidate(self, settings: dict) -> TradeCandidate | None:
        assets = database.get_enabled_assets(self.db_path)
        if not assets:
            logger.info("No enabled assets.")
            return None

        duration_seconds = safe_int(settings.get("trade_duration_seconds"), 180)
        min_confidence = safe_int(settings.get("min_confidence"), 80)
        min_payout = safe_float(settings.get("min_payout"), 0)
        profile = get_profile(duration_seconds)
        offset = max(3600, (profile["min_candles"] + 10) * 60)

        await self.ensure_client()
        best: TradeCandidate | None = None
        empty_candle_assets: list[str] = []
        empty_candle_limit = 1 if len(assets) == 1 else min(EMPTY_CANDLES_RECONNECT_LIMIT, len(assets))

        for asset in assets:
            asset_symbol = asset["symbol"]
            fixed_quotex_symbol = bool(asset["quotex_symbol"])
            quotex_symbol = asset["quotex_symbol"] or asset_symbol
            try:
                async with self.client_lock:
                    candles = await self.client.get_candles(quotex_symbol, period=60, offset=offset)
                if not candles:
                    empty_candle_assets.append(asset_symbol)
                    logger.info("Empty candles asset=%s empty_count=%s", asset_symbol, len(empty_candle_assets))
                    if len(empty_candle_assets) >= empty_candle_limit:
                        await self.reconnect_client(
                            f"empty candles for assets={','.join(empty_candle_assets)}"
                        )
                        return None
                    continue
            except QuotexAssetUnavailable as exc:
                logger.info("Skipping unavailable asset=%s reason=%s", asset_symbol, exc)
                continue
            except Exception:
                logger.exception("Failed to fetch candles asset=%s", asset_symbol)
                continue

            decision = analyze(
                asset=asset_symbol,
                candles=candles,
                duration_seconds=duration_seconds,
                min_confidence=min_confidence,
                drop_open_candle=True,
            )
            logger.info(
                "Decision asset=%s direction=%s confidence=%s reason=%s",
                asset_symbol,
                decision.direction,
                decision.confidence,
                decision.reason,
            )

            if decision.direction == NO_TRADE:
                continue
            payout = None
            if min_payout > 0:
                try:
                    async with self.client_lock:
                        payout = await self.client.get_payout(quotex_symbol, duration_seconds)
                except Exception:
                    logger.exception("Failed to read payout asset=%s", asset_symbol)
                    continue
                if payout is None:
                    logger.info("Skipping asset=%s because payout is unavailable min_payout=%s", asset_symbol, min_payout)
                    continue
                if payout < min_payout:
                    logger.info("Skipping asset=%s payout=%s below min_payout=%s", asset_symbol, payout, min_payout)
                    continue

            candidate = TradeCandidate(
                decision=decision,
                asset_symbol=asset_symbol,
                quotex_symbol=quotex_symbol,
                fixed_quotex_symbol=fixed_quotex_symbol,
                payout=payout,
            )
            if not best or candidate.decision.confidence > best.decision.confidence:
                best = candidate

        return best

    async def create_and_send_trade(self, candidate: TradeCandidate, settings: dict, entry_time: datetime) -> None:
        now = datetime.now(timezone.utc)
        duration_seconds = candidate.decision.duration_seconds
        expiry_time = entry_time + timedelta(seconds=duration_seconds)
        amount = safe_float(settings.get("trade_amount"), 0)
        account_type = settings.get("account_type", "DEMO").upper()
        indicators = candidate.decision.indicators
        execution_offset_ms = self.get_entry_offset_ms(candidate.asset_symbol, settings)

        if account_type != "DEMO":
            logger.warning("Auto buying blocked because account_type=%s. DEMO only is allowed.", account_type)
            return

        text = menu.format_signal(
            candidate.asset_symbol,
            candidate.decision.direction,
            format_entry_time(entry_time, settings.get("timezone", "Asia/Damascus")),
            max(1, duration_seconds // 60),
            candidate.decision.confidence,
        )
        message_refs = await self.send_to_signal_chats(text, parse_mode="Markdown")

        trade_id = database.create_trade(
            self.db_path,
            {
                "asset": candidate.asset_symbol,
                "direction": candidate.decision.direction,
                "signal_time": now.isoformat(timespec="seconds"),
                "entry_time": entry_time.isoformat(timespec="seconds"),
                "expiry_time": expiry_time.isoformat(timespec="seconds"),
                "duration_seconds": duration_seconds,
                "confidence": candidate.decision.confidence,
                "amount": amount,
                "account_type": "DEMO",
                "result": "PENDING",
                "profit_loss": 0,
                "rsi": candidate.decision.rsi,
                "ema_fast": candidate.decision.ema_fast,
                "ema_slow": candidate.decision.ema_slow,
                "ema_gap": indicators.get("ema_gap"),
                "adx": indicators.get("adx"),
                "atr": indicators.get("atr"),
                "payout": candidate.payout,
                "market_session": market_session(entry_time),
                "entry_delay_ms": None,
                "buy_latency_ms": None,
                "loss_streak": database.count_consecutive_losses(self.db_path),
                "candle_body_ratio": indicators.get("last_body_ratio"),
                "price_slippage": None,
                "websocket_latency": None,
                "broker_open_delay_ms": None,
                "execution_offset_ms": execution_offset_ms,
                "trend": candidate.decision.trend,
                "volatility": candidate.decision.volatility,
                "strategy_name": "ema_rsi_candle_v1",
                "decision_reason": candidate.decision.reason,
                "telegram_signal_message_id": ",".join(message_refs),
                "status": "SCHEDULED",
            },
        )
        logger.info(
            "Trade scheduled id=%s asset=%s direction=%s confidence=%s entry=%s expiry=%s",
            trade_id,
            candidate.asset_symbol,
            candidate.decision.direction,
            candidate.decision.confidence,
            entry_time.isoformat(),
            expiry_time.isoformat(),
        )

        task = asyncio.create_task(
            self.complete_trade(trade_id, candidate, entry_time, expiry_time, amount, execution_offset_ms)
        )
        self.trade_tasks.add(task)
        task.add_done_callback(self.trade_tasks.discard)

    async def complete_trade(
        self,
        trade_id: int,
        candidate: TradeCandidate,
        entry_time: datetime,
        expiry_time: datetime,
        amount: float,
        execution_offset_ms: int,
    ) -> None:
        try:
            await self.prepare_trade_entry(candidate, entry_time)
            send_time = entry_time - timedelta(milliseconds=execution_offset_ms)
            await self.sleep_until(send_time)
            entry_reached_at = datetime.now(timezone.utc)
            entry_send_delta_ms = (entry_reached_at - entry_time).total_seconds() * 1000
            entry_lag_ms = max(0, entry_send_delta_ms)
            logger.info(
                "Trade order send reached id=%s scheduled=%s send_target=%s actual=%s offset_ms=%s delta_ms=%.0f",
                trade_id,
                entry_time.isoformat(),
                send_time.isoformat(),
                entry_reached_at.isoformat(),
                execution_offset_ms,
                entry_send_delta_ms,
            )
            buy_started_at = datetime.now(timezone.utc)
            async with self.client_lock:
                buy_status, buy_info = await self.client.buy_demo(
                    amount,
                    candidate.quotex_symbol,
                    candidate.decision.direction,
                    candidate.decision.duration_seconds,
                    resolve=False,
                )

            order_id = extract_order_id(buy_info)
            buy_latency_ms = (datetime.now(timezone.utc) - buy_started_at).total_seconds() * 1000
            logger.info(
                "DEMO buy response id=%s status=%s order_id=%s latency_ms=%.0f",
                trade_id,
                buy_status,
                order_id,
                buy_latency_ms,
            )

            if not buy_status:
                database.update_trade(
                    self.db_path,
                    trade_id,
                    status="ERROR",
                    error_message=f"Quotex buy failed: {safe_json_dumps(buy_info)}",
                    quotex_buy_info=safe_json_dumps(buy_info),
                    entry_delay_ms=entry_lag_ms,
                    buy_latency_ms=buy_latency_ms,
                    execution_offset_ms=execution_offset_ms,
                )
                logger.warning("Trade buy failed id=%s response=%s", trade_id, safe_json_dumps(buy_info))
                if should_reconnect_after_error(buy_info):
                    await self.reconnect_client(f"buy failed id={trade_id} response={safe_json_dumps(buy_info)}")
                return

            open_price = extract_buy_number(buy_info, "openPrice", "open_price", "price")
            payout = extract_buy_number(buy_info, "percentProfit", "payout", "profit_percent")
            stored_payout = payout if payout is not None else candidate.payout
            entry_price = open_price if open_price is not None else await self.get_latest_price(candidate.quotex_symbol)
            price_slippage = calculate_price_slippage(candidate.pre_entry_price, open_price)
            broker_open_delay_ms = calculate_broker_open_delay_ms(buy_info, entry_time)
            database.update_trade(
                self.db_path,
                trade_id,
                entry_price=entry_price,
                quotex_order_id=order_id,
                quotex_buy_info=safe_json_dumps(buy_info),
                payout=stored_payout,
                entry_delay_ms=entry_lag_ms,
                buy_latency_ms=buy_latency_ms,
                price_slippage=price_slippage,
                broker_open_delay_ms=broker_open_delay_ms,
                execution_offset_ms=execution_offset_ms,
                status="OPEN",
            )
            logger.info(
                "DEMO trade opened id=%s order_id=%s entry_price=%s broker_open_delay_ms=%s offset_ms=%s",
                trade_id,
                order_id,
                entry_price,
                broker_open_delay_ms,
                execution_offset_ms,
            )
            self.adjust_entry_timing(candidate.asset_symbol, execution_offset_ms, broker_open_delay_ms)

            if order_id:
                async with self.client_lock:
                    raw_result, profit = await self.client.check_order_result(
                        order_id,
                        candidate.decision.duration_seconds,
                    )
                result = normalize_quotex_result(raw_result, profit)
                profit_loss = profit
                exit_price = await self.get_latest_price(candidate.quotex_symbol)
                if profit_loss == 0 and prices_equal(entry_price, exit_price):
                    result = "DRAW"
            else:
                await self.sleep_until(expiry_time + timedelta(seconds=2))
                exit_price = await self.get_latest_price(candidate.quotex_symbol)
                result = decide_result(candidate.decision.direction, entry_price, exit_price)
                profit_loss = calculate_profit_loss(result, amount)

            result_messages = await self.send_to_signal_chats(result_emoji(result))
            database.update_trade(
                self.db_path,
                trade_id,
                exit_price=exit_price,
                result=result,
                profit_loss=profit_loss,
                telegram_result_message_id=",".join(result_messages),
                status="CLOSED",
            )
            logger.info(
                "DEMO trade closed id=%s order_id=%s result=%s entry=%s exit=%s profit=%s",
                trade_id,
                order_id,
                result,
                entry_price,
                exit_price,
                profit_loss,
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("Trade lifecycle failed id=%s", trade_id)
            database.update_trade(self.db_path, trade_id, status="ERROR", error_message=str(exc))
            if should_reconnect_after_error(exc):
                await self.reconnect_client(f"trade lifecycle failed id={trade_id} error={exc}")

    def get_entry_offset_ms(self, asset_symbol: str, settings: dict) -> int:
        if settings.get("auto_entry_timing_enabled", "true").lower() != "true":
            return 0

        default_offset = safe_int(
            settings.get("auto_entry_default_offset_ms"),
            AUTO_ENTRY_DEFAULT_OFFSET_MS,
        )
        key = auto_entry_offset_key(asset_symbol)
        raw_offset = database.get_setting(self.db_path, key, default_offset)
        return clamp_int(safe_int(raw_offset, default_offset), 0, AUTO_ENTRY_MAX_OFFSET_MS)

    def adjust_entry_timing(self, asset_symbol: str, current_offset_ms: int, broker_open_delay_ms: float | None) -> None:
        if broker_open_delay_ms is None:
            return

        new_offset = current_offset_ms
        if broker_open_delay_ms < 0:
            new_offset -= min(300, int(abs(broker_open_delay_ms) + 150))
        elif broker_open_delay_ms < AUTO_ENTRY_TARGET_MIN_MS:
            new_offset -= min(200, int(AUTO_ENTRY_TARGET_MIN_MS - broker_open_delay_ms + 50))
        elif broker_open_delay_ms > AUTO_ENTRY_TARGET_MAX_MS:
            overshoot = broker_open_delay_ms - AUTO_ENTRY_TARGET_MAX_MS
            if overshoot > 700:
                new_offset += 150
            elif overshoot > 250:
                new_offset += 100
            else:
                new_offset += 50

        new_offset = clamp_int(new_offset, 0, AUTO_ENTRY_MAX_OFFSET_MS)
        if new_offset == current_offset_ms:
            return

        database.set_setting(self.db_path, auto_entry_offset_key(asset_symbol), new_offset)
        logger.info(
            "Auto entry timing adjusted asset=%s broker_delay_ms=%.0f old_offset_ms=%s new_offset_ms=%s",
            asset_symbol,
            broker_open_delay_ms,
            current_offset_ms,
            new_offset,
        )

    async def prepare_trade_entry(self, candidate: TradeCandidate, entry_time: datetime) -> None:
        warmup_time = entry_time - timedelta(seconds=12)
        await self.sleep_until(warmup_time)
        await self.ensure_client()
        async with self.client_lock:
            if not candidate.fixed_quotex_symbol:
                candidate.quotex_symbol = await self.client.resolve_asset(
                    candidate.quotex_symbol,
                    force_open=True,
                    require_available=True,
                )
            else:
                logger.info(
                    "Using fixed Quotex symbol asset=%s quotex_symbol=%s",
                    candidate.asset_symbol,
                    candidate.quotex_symbol,
                )
            try:
                candidate.pre_entry_price = await self.client.get_latest_price(candidate.quotex_symbol)
            except Exception:
                logger.exception("Failed to read pre-entry price asset=%s", candidate.asset_symbol)
        logger.info(
            "Trade prepared asset=%s quotex_symbol=%s entry=%s pre_entry_price=%s",
            candidate.asset_symbol,
            candidate.quotex_symbol,
            entry_time.isoformat(),
            candidate.pre_entry_price,
        )

    async def get_latest_price(self, asset: str) -> float:
        await self.ensure_client()
        async with self.client_lock:
            price = await self.client.get_latest_price(asset)
        if price is None:
            raise RuntimeError(f"Could not read latest price for {asset}")
        return price

    async def ensure_client(self) -> None:
        async with self.client_lock:
            if await self.client.check_connect():
                return
            await self.client.connect()

    async def reconnect_client(self, reason: str) -> None:
        logger.warning("Quotex reconnect requested reason=%s", reason)
        try:
            async with self.client_lock:
                await self.client.reconnect(reason)
        except Exception:
            logger.exception("Quotex reconnect failed reason=%s", reason)

    async def send_to_signal_chats(self, text: str, parse_mode: str | None = None) -> list[str]:
        chat_ids = database.get_signal_chat_ids(self.db_path)
        if not chat_ids:
            logger.warning("No signal chats configured.")
            return []

        refs = []
        for chat_id in chat_ids:
            try:
                message = await self.bot.send_message(chat_id, text, parse_mode=parse_mode)
                refs.append(f"{chat_id}:{message.message_id}")
            except Exception:
                logger.exception("Failed to send signal message chat_id=%s", chat_id)
        return refs

    async def sleep_until(self, target: datetime) -> None:
        while not self.stop_event.is_set():
            delay = (target - datetime.now(timezone.utc)).total_seconds()
            if delay <= 0:
                return
            if delay > 5:
                wait_time = 5
            elif delay > 1:
                wait_time = 0.25
            else:
                wait_time = max(0.01, min(delay, 0.05))
            await self.sleep(wait_time)

    async def sleep(self, seconds: float) -> None:
        try:
            await asyncio.wait_for(self.stop_event.wait(), timeout=seconds)
        except asyncio.TimeoutError:
            return


def is_signal_window(now: datetime, scan_interval_seconds: int) -> bool:
    return now.second <= max(2, scan_interval_seconds)


def floor_minute(value: datetime) -> datetime:
    return value.replace(second=0, microsecond=0)


def next_entry_time(now: datetime, min_notice_seconds: int = 10) -> datetime:
    entry_time = floor_minute(now) + timedelta(minutes=1)
    notice_seconds = (entry_time - now).total_seconds()
    if notice_seconds < min_notice_seconds:
        entry_time += timedelta(minutes=1)
    logger.info(
        "Next candle entry selected now=%s entry=%s notice_seconds=%.0f min_notice_seconds=%s",
        now.isoformat(),
        entry_time.isoformat(),
        (entry_time - now).total_seconds(),
        min_notice_seconds,
    )
    return entry_time


def format_entry_time(entry_time: datetime, timezone_name: str) -> str:
    try:
        tz = ZoneInfo(timezone_name)
    except Exception:
        tz = ZoneInfo("Asia/Damascus")
    local_time = entry_time.astimezone(tz)
    return local_time.strftime("%I:%M %p").lstrip("0")


def parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def market_session(entry_time: datetime) -> str:
    hour = entry_time.astimezone(timezone.utc).hour
    if 0 <= hour < 7:
        return "Asia"
    if 7 <= hour < 13:
        return "London"
    if 13 <= hour < 22:
        return "New York"
    return "Asia"


def extract_buy_number(value: Any, *keys: str) -> float | None:
    if isinstance(value, dict):
        for key in keys:
            raw = value.get(key)
            if raw is None:
                continue
            try:
                return float(raw)
            except (TypeError, ValueError):
                continue
        for child_key in ("data", "order", "result"):
            child = value.get(child_key)
            result = extract_buy_number(child, *keys)
            if result is not None:
                return result
    return None


def extract_buy_value(value: Any, *keys: str) -> Any:
    if isinstance(value, dict):
        for key in keys:
            if key in value and value[key] is not None:
                return value[key]
        for child_key in ("data", "order", "result"):
            child = value.get(child_key)
            result = extract_buy_value(child, *keys)
            if result is not None:
                return result
    return None


def calculate_broker_open_delay_ms(buy_info: Any, entry_time: datetime) -> float | None:
    open_time = parse_broker_open_time(buy_info)
    if open_time is None:
        return None
    open_ms = extract_buy_number(buy_info, "openMs", "open_ms")
    if open_ms is not None:
        open_time += timedelta(milliseconds=open_ms)
    return round((open_time - entry_time).total_seconds() * 1000, 3)


def parse_broker_open_time(buy_info: Any) -> datetime | None:
    raw_time = extract_buy_value(buy_info, "openTime", "open_time")
    if raw_time:
        text = str(raw_time).strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            try:
                parsed = datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                parsed = None
        if parsed is not None:
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)

    timestamp = extract_buy_number(buy_info, "openTimestamp", "open_timestamp")
    if timestamp is None:
        return None
    return datetime.fromtimestamp(timestamp, tz=timezone.utc)


def auto_entry_offset_key(asset_symbol: str) -> str:
    clean_symbol = asset_symbol.replace("/", "_").replace(" ", "_").upper()
    return f"auto_entry_offset_ms:{clean_symbol}"


def calculate_price_slippage(reference_price: float | None, open_price: float | None) -> float | None:
    if reference_price is None or open_price is None:
        return None
    return open_price - reference_price


def normalize_quotex_result(raw_result: str, profit: float | None = None) -> str:
    if profit is not None:
        if profit > 0:
            return "WIN"
        if profit < 0:
            return "LOSS"
        return "DRAW"

    value = (raw_result or "").lower()
    if value in {"win", "won", "profit"}:
        return "WIN"
    if value in {"draw", "equal"}:
        return "DRAW"
    return "LOSS"


def decide_result(direction: str, entry_price: float, exit_price: float) -> str:
    if prices_equal(entry_price, exit_price):
        return "DRAW"
    if direction == "CALL":
        return "WIN" if exit_price > entry_price else "LOSS"
    return "WIN" if exit_price < entry_price else "LOSS"


def prices_equal(entry_price: float, exit_price: float) -> bool:
    return abs(exit_price - entry_price) <= 1e-9


def result_emoji(result: str) -> str:
    return {"WIN": "✅", "LOSS": "❌", "DRAW": "🔄", "PENDING": "⏳"}.get(result, "⏳")


def calculate_profit_loss(result: str, amount: float) -> float:
    if result == "WIN":
        return amount
    if result == "LOSS":
        return -amount
    return 0


def should_reconnect_after_error(error: Any) -> bool:
    text = safe_json_dumps(error).lower()
    reconnect_markers = (
        "timeout",
        "timed out",
        "could not read latest price",
        "connection reset",
        "connection closed",
        "websocket",
        "close-wait",
    )
    return any(marker in text for marker in reconnect_markers)


def safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def safe_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def clamp_int(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(value, maximum))
