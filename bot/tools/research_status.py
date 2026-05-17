from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


BOT_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BOT_DIR / "data.db"

RESEARCH_TABLES = [
    "research_market_candles",
    "research_strategy_runs",
    "research_signals",
    "research_signal_outcomes",
    "research_analysis_runs",
]


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def table_exists(db: sqlite3.Connection, table_name: str) -> bool:
    row = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone()
    return row is not None


def scalar(db: sqlite3.Connection, query: str, params: tuple[Any, ...] = ()) -> Any:
    row = db.execute(query, params).fetchone()
    if not row:
        return None
    return row[0]


def count_table(db: sqlite3.Connection, table_name: str) -> int:
    if not table_exists(db, table_name):
        return 0
    return int(scalar(db, f"SELECT COUNT(*) FROM {table_name}") or 0)


def print_section(title: str) -> None:
    print("-" * 72)
    print(title)
    print("-" * 72)


def print_rows(title: str, rows: list[sqlite3.Row], columns: list[str]) -> None:
    print_section(title)
    if not rows:
        print("No data.")
        return
    print(" | ".join(columns))
    print(" | ".join("-" * len(column) for column in columns))
    for row in rows:
        print(" | ".join(str(row[column] if row[column] is not None else "") for column in columns))


def print_table_counts(db: sqlite3.Connection) -> None:
    print_section("Research table counts")
    for table in RESEARCH_TABLES:
        exists = table_exists(db, table)
        count = count_table(db, table)
        status = "ready" if exists else "missing"
        print(f"{table}: {count} rows ({status})")


def print_candle_status(db: sqlite3.Connection) -> None:
    if not table_exists(db, "research_market_candles"):
        print_section("Market candles")
        print("research_market_candles table is missing.")
        return

    print_section("Market candles")
    total = count_table(db, "research_market_candles")
    sources = scalar(db, "SELECT COUNT(DISTINCT source_key) FROM research_market_candles") or 0
    assets = scalar(db, "SELECT COUNT(DISTINCT asset) FROM research_market_candles") or 0
    timeframes = scalar(db, "SELECT COUNT(DISTINCT timeframe_seconds) FROM research_market_candles") or 0
    first_time = scalar(db, "SELECT MIN(candle_time) FROM research_market_candles") or ""
    last_time = scalar(db, "SELECT MAX(candle_time) FROM research_market_candles") or ""
    print(f"Total candles: {total}")
    print(f"Sources: {sources}")
    print(f"Assets: {assets}")
    print(f"Timeframes: {timeframes}")
    print(f"First candle: {first_time}")
    print(f"Last candle: {last_time}")

    rows = db.execute(
        """
        SELECT source_key,
               asset,
               timeframe_seconds,
               COUNT(*) AS candles,
               MIN(candle_time) AS first_time,
               MAX(candle_time) AS last_time
        FROM research_market_candles
        GROUP BY source_key, asset, timeframe_seconds
        ORDER BY candles DESC, source_key, asset
        LIMIT 12
        """
    ).fetchall()
    print_rows(
        "Market candle groups, top 12",
        rows,
        ["source_key", "asset", "timeframe_seconds", "candles", "first_time", "last_time"],
    )


def print_signal_status(db: sqlite3.Connection) -> None:
    if not table_exists(db, "research_signals"):
        print_section("Research signals")
        print("research_signals table is missing.")
        return

    print_section("Research signals")
    total = count_table(db, "research_signals")
    with_outcome = 0
    if table_exists(db, "research_signal_outcomes"):
        with_outcome = int(
            scalar(
                db,
                """
                SELECT COUNT(*)
                FROM research_signals s
                INNER JOIN research_signal_outcomes o ON o.signal_id = s.id
                """,
            )
            or 0
        )
    without_outcome = max(0, total - with_outcome)
    first_signal = scalar(db, "SELECT MIN(signal_time) FROM research_signals") or ""
    last_signal = scalar(db, "SELECT MAX(signal_time) FROM research_signals") or ""
    print(f"Total signals: {total}")
    print(f"Signals with outcome: {with_outcome}")
    print(f"Signals pending outcome: {without_outcome}")
    print(f"First signal: {first_signal}")
    print(f"Last signal: {last_signal}")

    rows = db.execute(
        """
        SELECT strategy_name,
               direction,
               COUNT(*) AS signals,
               ROUND(AVG(confidence), 2) AS avg_confidence
        FROM research_signals
        GROUP BY strategy_name, direction
        ORDER BY signals DESC
        LIMIT 12
        """
    ).fetchall()
    print_rows(
        "Signal groups, top 12",
        rows,
        ["strategy_name", "direction", "signals", "avg_confidence"],
    )


def print_outcome_status(db: sqlite3.Connection) -> None:
    if not table_exists(db, "research_signal_outcomes"):
        print_section("Signal outcomes")
        print("research_signal_outcomes table is missing.")
        return

    rows = db.execute(
        """
        SELECT result,
               COUNT(*) AS outcomes,
               ROUND(SUM(COALESCE(theoretical_profit_loss, 0)), 2) AS theoretical_profit_loss
        FROM research_signal_outcomes
        GROUP BY result
        ORDER BY outcomes DESC
        """
    ).fetchall()
    print_rows("Signal outcome breakdown", rows, ["result", "outcomes", "theoretical_profit_loss"])


def print_decision(db: sqlite3.Connection) -> None:
    print_section("Research readiness")
    candles = count_table(db, "research_market_candles")
    signals = count_table(db, "research_signals")
    outcomes = count_table(db, "research_signal_outcomes")

    if candles == 0 and signals == 0:
        print("READY FOR NEXT BUILD STEP: tables exist, but no signal-only market data has been collected yet.")
        print("Next needed layer: read-only market source adapter or replay importer.")
    elif candles > 0 and signals == 0:
        print("PARTIAL: candles exist, but no strategy signals have been generated yet.")
        print("Next needed layer: signal-only strategy runner.")
    elif signals > 0 and outcomes == 0:
        print("PARTIAL: signals exist, but outcomes have not been evaluated yet.")
        print("Next needed layer: signal outcome evaluator.")
    else:
        print("RESEARCH DATA EXISTS: review analysis reports before changing any strategy or scanner setting.")
    print("Automatic buying remains outside this research flow.")


def main() -> int:
    print("=" * 72)
    print("QTB signal-only research status")
    print("=" * 72)
    print(f"Database: {DB_PATH}")
    print("This reads research_* tables only. It does not start the bot or trade.")

    if not DB_PATH.exists():
        print("Database not found. Run project setup or init_signal_research_tables first.")
        return 1

    with connect() as db:
        print_table_counts(db)
        print_candle_status(db)
        print_signal_status(db)
        print_outcome_status(db)
        print_decision(db)

    print("=" * 72)
    print("Research status finished. No secrets were printed and no native trades were changed.")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
