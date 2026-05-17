from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable


BOT_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BOT_DIR / "data.db"
EXPORT_DIR = BOT_DIR / "exports"
PAPER_STRATEGY = "paper_simulated_v1"
PAPER_REASON_PREFIX = "SIMULATED PAPER DATA"


def connect(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection


def table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    row = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def scalar(connection: sqlite3.Connection, sql: str, params: Iterable[object] = ()) -> int | float | str | None:
    row = connection.execute(sql, tuple(params)).fetchone()
    if not row:
        return None
    return row[0]


def count_where(connection: sqlite3.Connection, where_sql: str = "1=1", params: Iterable[object] = ()) -> int:
    value = scalar(connection, f"SELECT COUNT(*) FROM trades WHERE {where_sql}", params)
    return int(value or 0)


def count_table(connection: sqlite3.Connection, table_name: str) -> int:
    if not table_exists(connection, table_name):
        return 0
    value = scalar(connection, f"SELECT COUNT(*) FROM {table_name}")
    return int(value or 0)


def setting(connection: sqlite3.Connection, key: str, default: str = "") -> str:
    if not table_exists(connection, "bot_settings"):
        return default
    row = connection.execute("SELECT value FROM bot_settings WHERE key = ?", (key,)).fetchone()
    return str(row["value"]) if row else default


def quotex_source_status(connection: sqlite3.Connection) -> tuple[str, str]:
    if not table_exists(connection, "quotex_accounts"):
        return "MISSING", "quotex_accounts table is missing"

    row = connection.execute(
        "SELECT email, password, account_type, enabled FROM quotex_accounts WHERE id = 1"
    ).fetchone()
    if not row:
        return "MISSING", "local Quotex account row is missing"

    has_email = bool(row["email"])
    has_password = bool(row["password"])
    enabled = int(row["enabled"] or 0) == 1
    account_type = str(row["account_type"] or "DEMO")

    if has_email and has_password and enabled:
        return "CONFIGURED", f"local source configured, account_type={account_type}"
    if has_email and has_password and not enabled:
        return "DISABLED", f"local source values exist but account is disabled, account_type={account_type}"
    return "MISSING", "local Quotex source is not configured"


def latest_exports() -> list[Path]:
    if not EXPORT_DIR.exists():
        return []
    return sorted(EXPORT_DIR.glob("*.csv"), key=lambda path: path.stat().st_mtime, reverse=True)[:5]


def print_header(title: str) -> None:
    print()
    print("-" * 72)
    print(title)
    print("-" * 72)


def main() -> int:
    print("=" * 72)
    print("QTB local data quality report")
    print("=" * 72)

    if not DB_PATH.exists():
        print(f"Database: MISSING ({DB_PATH})")
        print("Result: NOT READY - run the bot check or initialize the database first.")
        return 1

    print(f"Database: found ({DB_PATH})")

    with connect(DB_PATH) as connection:
        scanner_value = setting(connection, "bot_enabled", "false").lower()
        scanner_status = "RUNNING" if scanner_value == "true" else "STOPPED"
        auto_buy_value = setting(connection, "auto_buy_enabled", "false").lower()
        auto_buy_status = "ENABLED" if auto_buy_value == "true" else "DISABLED"
        source_status, source_detail = quotex_source_status(connection)

        print_header("Runtime state")
        print(f"DEMO scanner: {scanner_status} (bot_enabled={scanner_value})")
        print(f"Automatic DEMO buying: {auto_buy_status} (auto_buy_enabled={auto_buy_value})")
        print(f"Market data source: {source_status}")
        print(f"Source detail: {source_detail}")

        if not table_exists(connection, "trades"):
            print_header("Trade data")
            print("Trades table: MISSING")
            print("Result: NOT READY - no trade table exists yet.")
            return 1

        total = count_where(connection)
        closed = count_where(connection, "status = 'CLOSED'")
        signal_only = count_where(connection, "status = 'SIGNAL_ONLY'")
        open_count = count_where(connection, "status IN ('OPEN', 'SCHEDULED')")
        errors = count_where(connection, "status = 'ERROR' OR error_message IS NOT NULL")
        paper = count_where(
            connection,
            "strategy_name = ? OR decision_reason LIKE ?",
            (PAPER_STRATEGY, f"{PAPER_REASON_PREFIX}%"),
        )
        real_demo = max(0, total - paper - signal_only)

        print_header("Trade data")
        print(f"Total trades: {total}")
        print(f"Closed trades: {closed}")
        print(f"Signal-only records: {signal_only}")
        print(f"Open/scheduled trades: {open_count}")
        print(f"Error trades: {errors}")
        print(f"Simulated paper trades: {paper}")
        print(f"Executed/non-paper DEMO records: {real_demo}")

        if total:
            status_rows = connection.execute(
                "SELECT COALESCE(status, 'UNKNOWN') AS status, COUNT(*) AS total FROM trades GROUP BY status ORDER BY total DESC"
            ).fetchall()
            print("Status breakdown:")
            for row in status_rows:
                print(f"  - {row['status']}: {row['total']}")

            strategy_rows = connection.execute(
                "SELECT COALESCE(strategy_name, 'UNKNOWN') AS strategy, COUNT(*) AS total FROM trades GROUP BY strategy_name ORDER BY total DESC LIMIT 10"
            ).fetchall()
            print("Strategy breakdown:")
            for row in strategy_rows:
                print(f"  - {row['strategy']}: {row['total']}")

        print_header("External research data")
        datasets = count_table(connection, "external_datasets")
        external_trades = count_table(connection, "external_trades")
        external_strategies = count_table(connection, "external_strategies")
        print(f"External datasets: {datasets}")
        print(f"External trades: {external_trades}")
        print(f"External strategies: {external_strategies}")
        if not table_exists(connection, "external_datasets"):
            print("Research tables: not initialized yet. Run init_research_tables when needed.")
        elif datasets == 0:
            print("Research tables: initialized, no external data imported yet.")

        print_header("Signal-only research data")
        research_candles = count_table(connection, "research_market_candles")
        research_runs = count_table(connection, "research_strategy_runs")
        research_signals = count_table(connection, "research_signals")
        research_outcomes = count_table(connection, "research_signal_outcomes")
        research_analysis = count_table(connection, "research_analysis_runs")
        print(f"Research candles: {research_candles}")
        print(f"Research strategy runs: {research_runs}")
        print(f"Research signals: {research_signals}")
        print(f"Research signal outcomes: {research_outcomes}")
        print(f"Research analysis runs: {research_analysis}")
        if not table_exists(connection, "research_market_candles"):
            print("Signal research tables: not initialized yet. Run init_signal_research_tables when needed.")
        elif research_candles == 0 and research_signals == 0:
            print("Signal research tables: initialized, no signal-only market data collected yet.")

        print_header("Exports")
        exports = latest_exports()
        if not exports:
            print("No CSV exports found yet.")
        else:
            for path in exports:
                print(f"- {path.name} ({path.stat().st_size} bytes)")

        print_header("Readiness result")
        if auto_buy_status == "ENABLED":
            print("SAFETY WARNING: automatic DEMO buying is enabled. Disable it before market-source testing.")
        if source_status == "MISSING":
            print("NOT READY for real DEMO data collection: market data source is missing.")
        elif source_status == "DISABLED":
            print("NOT READY for real DEMO data collection: market data source is disabled.")
        elif scanner_status == "STOPPED":
            print("READY TO START after review: market data source exists, but scanner is currently stopped.")
        else:
            print("RUNNING: scanner is enabled and a market data source is configured.")

        if paper > 0 and real_demo == 0 and signal_only == 0:
            print("Note: database currently contains only simulated paper records.")
        elif paper > 0 and (real_demo > 0 or signal_only > 0):
            print("Warning: database contains mixed paper and non-paper records. Separate them before evaluation.")
        elif total == 0:
            print("Note: database has no trades yet.")
        if external_trades > 0:
            print("Note: external research records are separate from native trades.")
        if research_candles > 0 or research_signals > 0:
            print("Note: signal-only research records are separate from native trades.")

    print()
    print("=" * 72)
    print("Data quality report finished. No secrets were printed.")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())