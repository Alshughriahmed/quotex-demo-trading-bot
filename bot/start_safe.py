from __future__ import annotations

import runpy
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import database
from trading.quotex_client import QuotexClient
from trading.trader import TradingRunner, audit_decision


BOT_DIR = Path(__file__).resolve().parent
MAIN_PATH = BOT_DIR / "main.py"
DB_PATH = BOT_DIR / "data.db"
_original_buy_demo = QuotexClient.buy_demo
_original_complete_trade = TradingRunner.complete_trade


async def guarded_buy_demo(self: QuotexClient, *args: Any, **kwargs: Any) -> tuple[bool, dict[str, Any]]:
    setting = database.get_setting(self.db_path, "auto_buy_enabled", "false")
    if str(setting).lower() != "true":
        return False, {
            "error": "auto_buy_disabled",
            "message": "Automatic DEMO buying is disabled by local safety guard.",
        }
    return await _original_buy_demo(self, *args, **kwargs)


async def signal_only_complete_trade(
    self: TradingRunner,
    trade_id: int,
    candidate: Any,
    entry_time: datetime,
    expiry_time: datetime,
    amount: float,
    execution_offset_ms: int,
) -> None:
    setting = database.get_setting(self.db_path, "auto_buy_enabled", "false")
    if str(setting).lower() == "true":
        await _original_complete_trade(
            self,
            trade_id,
            candidate,
            entry_time,
            expiry_time,
            amount,
            execution_offset_ms,
        )
        return

    audit_decision(
        "blocked",
        trade_id=trade_id,
        reason="auto_buy_disabled",
        mode="signal_only",
        asset=candidate.asset_symbol,
        direction=candidate.decision.direction,
    )
    database.update_trade(
        self.db_path,
        trade_id,
        status="SIGNAL_ONLY",
        error_message="auto_buy_disabled: signal was sent, but automatic DEMO buying is disabled.",
        entry_delay_ms=None,
        buy_latency_ms=None,
        execution_offset_ms=execution_offset_ms,
    )
    print(
        "Signal-only guard: trade "
        f"{trade_id} was not executed because auto_buy_enabled=false "
        f"at {datetime.now(timezone.utc).isoformat(timespec='seconds')}"
    )


def install_runtime_guards() -> None:
    QuotexClient.buy_demo = guarded_buy_demo
    TradingRunner.complete_trade = signal_only_complete_trade


def table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    row = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def market_source_configured(connection: sqlite3.Connection) -> bool:
    if not table_exists(connection, "quotex_accounts"):
        return False
    row = connection.execute(
        "SELECT email, password, enabled FROM quotex_accounts WHERE id = 1"
    ).fetchone()
    if not row:
        return False
    return bool(row[0] and row[1] and int(row[2] or 0) == 1)


def enforce_startup_state() -> None:
    if not DB_PATH.exists():
        return
    with sqlite3.connect(DB_PATH) as connection:
        if not table_exists(connection, "bot_settings"):
            return
        scanner_row = connection.execute(
            "SELECT value FROM bot_settings WHERE key = 'bot_enabled'"
        ).fetchone()
        scanner_enabled = bool(scanner_row and str(scanner_row[0]).lower() == "true")
        if scanner_enabled and not market_source_configured(connection):
            connection.execute(
                """
                INSERT INTO bot_settings(key, value, value_type, description)
                VALUES ('bot_enabled', 'false', 'bool', 'تشغيل أو إيقاف البوت')
                ON CONFLICT(key) DO UPDATE SET
                    value = 'false',
                    value_type = 'bool',
                    description = 'تشغيل أو إيقاف البوت',
                    updated_at = CURRENT_TIMESTAMP
                """
            )
            connection.commit()
            print("Startup guard: scanner was stopped because market data source is missing.")


def main() -> int:
    install_runtime_guards()
    enforce_startup_state()
    print("Safe launcher active: auto-buy guard is enforced.")
    print("Signal-only guard active: signals can be recorded without automatic DEMO buying.")
    runpy.run_path(str(MAIN_PATH), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
