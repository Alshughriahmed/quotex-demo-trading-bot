from __future__ import annotations

import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


BOT_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BOT_DIR / "data.db"
TEST_SOURCE_KEY = "replay_outcome_evaluator_check"
TEST_ASSET = "EUR/USD"
TEST_TIMEFRAME = 60
TEST_DURATION = 60
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
    for index in range(40):
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


def cleanup() -> None:
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
        db.commit()


def count_table(table: str, where: str = "1=1", params: tuple[object, ...] = ()) -> int:
    with sqlite3.connect(DB_PATH) as db:
        row = db.execute(f"SELECT COUNT(*) FROM {table} WHERE {where}", params).fetchone()
        return int(row[0] or 0)


def run_signal_runner(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
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
            *args,
        ],
        cwd=BOT_DIR,
        text=True,
        capture_output=True,
        check=False,
    )


def run_evaluator(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "tools/evaluate_replay_outcomes.py",
            "--source-key",
            TEST_SOURCE_KEY,
            "--asset",
            TEST_ASSET,
            "--payout",
            "0.80",
            *args,
        ],
        cwd=BOT_DIR,
        text=True,
        capture_output=True,
        check=False,
    )


def print_process_result(title: str, result: subprocess.CompletedProcess[str]) -> None:
    print("-" * 72)
    print(title)
    print("-" * 72)
    print(f"Return code: {result.returncode}")
    if result.stdout.strip():
        print(result.stdout.strip())
    if result.stderr.strip():
        print("stderr:")
        print(result.stderr.strip())


def outcome_breakdown() -> dict[str, int]:
    with sqlite3.connect(DB_PATH) as db:
        rows = db.execute(
            """
            SELECT o.result, COUNT(*)
            FROM research_signal_outcomes o
            INNER JOIN research_signals s ON s.id = o.signal_id
            WHERE s.source_key = ?
            GROUP BY o.result
            """,
            (TEST_SOURCE_KEY,),
        ).fetchall()
    return {str(result): int(count) for result, count in rows}


def main() -> int:
    print("=" * 72)
    print("QTB replay outcome evaluator smoke check")
    print("=" * 72)
    print("This inserts dummy candles/signals, previews outcome evaluation, inserts outcomes, then cleans everything up.")
    print("It does not start the bot, does not connect to a broker, and does not trade.")
    print(f"Database: {DB_PATH}")

    if not DB_PATH.exists():
        print("Database not found. Run init_signal_research_tables first.")
        return 1

    cleanup()
    try:
        candles = sample_candles()
        stored = store_market_candles(DB_PATH, candles)
        candle_count = count_table("research_market_candles", "source_key = ?", (TEST_SOURCE_KEY,))
        print(f"Dummy candles stored: {stored}")
        print(f"Dummy candle rows present: {candle_count}")
        if candle_count != len(candles):
            print("Result: FAILED - dummy candles were not stored correctly.")
            return 1

        signal_run = run_signal_runner("--yes")
        print_process_result("Signal insert run", signal_run)
        if signal_run.returncode != 0:
            print("Result: FAILED - signal insert run failed.")
            return 1

        signal_count = count_table("research_signals", "source_key = ?", (TEST_SOURCE_KEY,))
        if signal_count != EXPECTED_SIGNALS:
            print(f"Result: FAILED - expected {EXPECTED_SIGNALS} research signals, got {signal_count}.")
            return 1

        dry_run = run_evaluator()
        print_process_result("Outcome dry run", dry_run)
        if dry_run.returncode != 0:
            print("Result: FAILED - outcome dry run failed.")
            return 1
        if count_table(
            "research_signal_outcomes",
            "signal_id IN (SELECT id FROM research_signals WHERE source_key = ?)",
            (TEST_SOURCE_KEY,),
        ) != 0:
            print("Result: FAILED - outcome dry run inserted rows.")
            return 1

        evaluate_run = run_evaluator("--yes")
        print_process_result("Outcome insert run", evaluate_run)
        if evaluate_run.returncode != 0:
            print("Result: FAILED - outcome insert run failed.")
            return 1

        outcome_count = count_table(
            "research_signal_outcomes",
            "signal_id IN (SELECT id FROM research_signals WHERE source_key = ?)",
            (TEST_SOURCE_KEY,),
        )
        breakdown = outcome_breakdown()
        cleanup()
        after_candles = count_table("research_market_candles", "source_key = ?", (TEST_SOURCE_KEY,))
        after_signals = count_table("research_signals", "source_key = ?", (TEST_SOURCE_KEY,))
        after_outcomes = count_table(
            "research_signal_outcomes",
            "signal_id IN (SELECT id FROM research_signals WHERE source_key = ?)",
            (TEST_SOURCE_KEY,),
        )
        after_runs = count_table("research_strategy_runs", "source_key = ?", (TEST_SOURCE_KEY,))

        print("-" * 72)
        print("Verification")
        print("-" * 72)
        print(f"Research signals inserted: {signal_count}")
        print(f"Research outcomes inserted: {outcome_count}")
        print(f"Outcome breakdown: {breakdown}")
        print(f"Rows after cleanup - candles/signals/outcomes/runs: {after_candles}/{after_signals}/{after_outcomes}/{after_runs}")

        if outcome_count != EXPECTED_OUTCOMES:
            print(f"Result: FAILED - expected {EXPECTED_OUTCOMES} outcomes, got {outcome_count}.")
            return 1
        if breakdown.get("WIN", 0) != EXPECTED_OUTCOMES:
            print("Result: FAILED - expected all evaluable dummy CALL signals to be WIN.")
            return 1
        if after_candles != 0 or after_signals != 0 or after_outcomes != 0 or after_runs != 0:
            print("Result: FAILED - cleanup did not remove dummy rows.")
            return 1

        print("Result: PASSED")
        print("Replay outcome evaluator can preview, insert, and clean dummy outcomes.")
        print("No native trades were changed.")
        print("=" * 72)
        return 0
    finally:
        cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
