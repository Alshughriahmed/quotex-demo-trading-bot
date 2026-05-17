from __future__ import annotations

import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


BOT_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BOT_DIR / "data.db"
TEST_SOURCE_KEY = "replay_report_check"
TEST_ASSET = "EUR/USD"
TEST_TIMEFRAME = 60
TEST_DURATION = 60
EXPECTED_CANDLES = 40
EXPECTED_SIGNALS = 6
EXPECTED_OUTCOMES = 5

if str(BOT_DIR) not in sys.path:
    sys.path.insert(0, str(BOT_DIR))

from market_sources import MarketCandle
from research import store_market_candles


def sample_candles() -> list[MarketCandle]:
    start = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    candles: list[MarketCandle] = []
    price = 1.1000
    for index in range(EXPECTED_CANDLES):
        open_price = price
        close_price = price + 0.00008
        high_price = close_price + 0.00004
        low_price = open_price - 0.00004
        candles.append(
            MarketCandle(
                source_key=TEST_SOURCE_KEY,
                asset=TEST_ASSET,
                timeframe_seconds=TEST_TIMEFRAME,
                candle_time=start + timedelta(seconds=TEST_TIMEFRAME * index),
                open=round(open_price, 6),
                high=round(high_price, 6),
                low=round(low_price, 6),
                close=round(close_price, 6),
                volume=None,
                is_closed=True,
            )
        )
        price = close_price
    return candles


def scalar(query: str, params: tuple[object, ...] = ()) -> object:
    with sqlite3.connect(DB_PATH) as db:
        row = db.execute(query, params).fetchone()
        return row[0] if row else None


def count_table(table: str, where: str = "1=1", params: tuple[object, ...] = ()) -> int:
    return int(scalar(f"SELECT COUNT(*) FROM {table} WHERE {where}", params) or 0)


def max_analysis_id() -> int:
    return int(scalar("SELECT COALESCE(MAX(id), 0) FROM research_analysis_runs") or 0)


def cleanup(analysis_baseline_id: int | None = None) -> None:
    if not DB_PATH.exists():
        return
    with sqlite3.connect(DB_PATH) as db:
        signal_ids = [
            row[0]
            for row in db.execute(
                "SELECT id FROM research_signals WHERE source_key = ?",
                (TEST_SOURCE_KEY,),
            ).fetchall()
        ]
        if signal_ids:
            placeholders = ",".join("?" for _ in signal_ids)
            db.execute(f"DELETE FROM research_signal_outcomes WHERE signal_id IN ({placeholders})", signal_ids)
            db.execute(f"DELETE FROM research_signals WHERE id IN ({placeholders})", signal_ids)
        db.execute("DELETE FROM research_strategy_runs WHERE source_key = ?", (TEST_SOURCE_KEY,))
        db.execute("DELETE FROM research_market_candles WHERE source_key = ?", (TEST_SOURCE_KEY,))
        if analysis_baseline_id is not None:
            db.execute("DELETE FROM research_analysis_runs WHERE id > ?", (analysis_baseline_id,))
        db.commit()


def run_command(title: str, args: list[str]) -> subprocess.CompletedProcess[str]:
    print("-" * 72)
    print(title)
    print("-" * 72)
    result = subprocess.run(args, cwd=BOT_DIR, text=True, capture_output=True, check=False)
    print(f"Return code: {result.returncode}")
    if result.stdout.strip():
        print(result.stdout.strip())
    if result.stderr.strip():
        print("stderr:")
        print(result.stderr.strip())
    return result


def run_signal_runner() -> subprocess.CompletedProcess[str]:
    return run_command(
        "Create dummy replay signals",
        [
            sys.executable,
            "tools/run_replay_signals.py",
            "--source-key",
            TEST_SOURCE_KEY,
            "--asset",
            TEST_ASSET,
            "--timeframe",
            str(TEST_TIMEFRAME),
            "--duration",
            str(TEST_DURATION),
            "--include-no-trade",
            "--yes",
        ],
    )


def run_outcome_evaluator() -> subprocess.CompletedProcess[str]:
    return run_command(
        "Evaluate dummy replay outcomes",
        [
            sys.executable,
            "tools/evaluate_replay_outcomes.py",
            "--source-key",
            TEST_SOURCE_KEY,
            "--asset",
            TEST_ASSET,
            "--payout",
            "0.80",
            "--yes",
        ],
    )


def run_report() -> subprocess.CompletedProcess[str]:
    return run_command(
        "Run replay research report",
        [sys.executable, "tools/replay_research_report.py"],
    )


def main() -> int:
    print("=" * 72)
    print("QTB replay research report smoke check")
    print("=" * 72)
    print("This creates dummy replay research rows, runs the report, then cleans all dummy rows.")
    print("It does not start the bot, does not connect to a broker, and does not trade.")
    print(f"Database: {DB_PATH}")

    if not DB_PATH.exists():
        print("Database not found. Run init_signal_research_tables first.")
        return 1

    analysis_baseline_id = max_analysis_id()
    cleanup(analysis_baseline_id)
    try:
        candles = sample_candles()
        stored = store_market_candles(DB_PATH, candles)
        candle_count = count_table("research_market_candles", "source_key = ?", (TEST_SOURCE_KEY,))
        print(f"Dummy candles stored: {stored}")
        print(f"Dummy candle rows present: {candle_count}")
        if candle_count != EXPECTED_CANDLES:
            print("Result: FAILED - dummy candles were not stored correctly.")
            return 1

        signal_run = run_signal_runner()
        if signal_run.returncode != 0:
            print("Result: FAILED - signal runner failed.")
            return 1
        signal_count = count_table("research_signals", "source_key = ?", (TEST_SOURCE_KEY,))
        if signal_count != EXPECTED_SIGNALS:
            print(f"Result: FAILED - expected {EXPECTED_SIGNALS} signals, got {signal_count}.")
            return 1

        outcome_run = run_outcome_evaluator()
        if outcome_run.returncode != 0:
            print("Result: FAILED - outcome evaluator failed.")
            return 1
        outcome_count = count_table(
            "research_signal_outcomes",
            "signal_id IN (SELECT id FROM research_signals WHERE source_key = ?)",
            (TEST_SOURCE_KEY,),
        )
        if outcome_count != EXPECTED_OUTCOMES:
            print(f"Result: FAILED - expected {EXPECTED_OUTCOMES} outcomes, got {outcome_count}.")
            return 1

        report_run = run_report()
        if report_run.returncode != 0:
            print("Result: FAILED - report failed.")
            return 1
        if "Research outcomes: 5" not in report_run.stdout or "Theoretical profit/loss: 4.00" not in report_run.stdout:
            print("Result: FAILED - report output did not include expected dummy summary.")
            return 1

        new_analysis_rows = count_table("research_analysis_runs", "id > ?", (analysis_baseline_id,))
        cleanup(analysis_baseline_id)

        after_candles = count_table("research_market_candles", "source_key = ?", (TEST_SOURCE_KEY,))
        after_signals = count_table("research_signals", "source_key = ?", (TEST_SOURCE_KEY,))
        after_outcomes = count_table(
            "research_signal_outcomes",
            "signal_id IN (SELECT id FROM research_signals WHERE source_key = ?)",
            (TEST_SOURCE_KEY,),
        )
        after_runs = count_table("research_strategy_runs", "source_key = ?", (TEST_SOURCE_KEY,))
        after_analysis_rows = count_table("research_analysis_runs", "id > ?", (analysis_baseline_id,))

        print("-" * 72)
        print("Verification")
        print("-" * 72)
        print(f"Candles/signals/outcomes before cleanup: {candle_count}/{signal_count}/{outcome_count}")
        print(f"Temporary analysis rows created: {new_analysis_rows}")
        print(f"Rows after cleanup - candles/signals/outcomes/runs/analysis: {after_candles}/{after_signals}/{after_outcomes}/{after_runs}/{after_analysis_rows}")

        if after_candles != 0 or after_signals != 0 or after_outcomes != 0 or after_runs != 0 or after_analysis_rows != 0:
            print("Result: FAILED - cleanup did not remove dummy report rows.")
            return 1

        print("Result: PASSED")
        print("Replay research report works on evaluated dummy outcomes and cleans up correctly.")
        print("No native trades were changed.")
        print("=" * 72)
        return 0
    finally:
        cleanup(analysis_baseline_id)


if __name__ == "__main__":
    raise SystemExit(main())
