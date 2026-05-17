from __future__ import annotations

import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


BOT_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BOT_DIR / "data.db"
TEMP_CSV = BOT_DIR / "external_inputs" / "replay_pipeline_check.csv"
TEST_SOURCE_KEY = "replay_pipeline_check"
TEST_ASSET = "EUR/USD"
TEST_TIMEFRAME = 60
TEST_DURATION = 60
EXPECTED_CANDLES = 40
EXPECTED_SIGNALS = 6
EXPECTED_OUTCOMES = 5


def build_csv_content() -> str:
    start = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    rows = ["source_key,asset,timeframe_seconds,candle_time,open,high,low,close,volume,is_closed"]
    price = 1.1000
    for index in range(EXPECTED_CANDLES):
        open_price = price
        close_price = price + 0.00008
        high_price = close_price + 0.00004
        low_price = open_price - 0.00004
        candle_time = (start + timedelta(seconds=TEST_TIMEFRAME * index)).isoformat().replace("+00:00", "Z")
        rows.append(
            f"{TEST_SOURCE_KEY},{TEST_ASSET},{TEST_TIMEFRAME},{candle_time},"
            f"{open_price:.6f},{high_price:.6f},{low_price:.6f},{close_price:.6f},,true"
        )
        price = close_price
    return "\n".join(rows) + "\n"


def cleanup() -> None:
    if DB_PATH.exists():
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
    try:
        TEMP_CSV.unlink(missing_ok=True)
    except OSError:
        pass


def count_table(table: str, where: str = "1=1", params: tuple[object, ...] = ()) -> int:
    with sqlite3.connect(DB_PATH) as db:
        row = db.execute(f"SELECT COUNT(*) FROM {table} WHERE {where}", params).fetchone()
        return int(row[0] or 0)


def outcome_count() -> int:
    return count_table(
        "research_signal_outcomes",
        "signal_id IN (SELECT id FROM research_signals WHERE source_key = ?)",
        (TEST_SOURCE_KEY,),
    )


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


def main() -> int:
    print("=" * 72)
    print("QTB end-to-end replay research pipeline check")
    print("=" * 72)
    print("This creates a temporary CSV, imports candles, creates signals, evaluates outcomes, then cleans up.")
    print("It does not start the bot, does not connect to a broker, and does not trade.")
    print(f"Database: {DB_PATH}")

    if not DB_PATH.exists():
        print("Database not found. Run init_signal_research_tables first.")
        return 1

    cleanup()
    try:
        TEMP_CSV.parent.mkdir(parents=True, exist_ok=True)
        TEMP_CSV.write_text(build_csv_content(), encoding="utf-8")
        print(f"Temporary CSV created: {TEMP_CSV}")

        import_result = run_command(
            "Import replay candles",
            [sys.executable, "tools/import_replay_candles.py", str(TEMP_CSV), "--yes"],
        )
        if import_result.returncode != 0:
            print("Result: FAILED - replay candle import failed.")
            return 1
        candle_count = count_table("research_market_candles", "source_key = ?", (TEST_SOURCE_KEY,))
        if candle_count != EXPECTED_CANDLES:
            print(f"Result: FAILED - expected {EXPECTED_CANDLES} candles, got {candle_count}.")
            return 1

        signal_result = run_command(
            "Run replay signals",
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
        if signal_result.returncode != 0:
            print("Result: FAILED - replay signal runner failed.")
            return 1
        signal_count = count_table("research_signals", "source_key = ?", (TEST_SOURCE_KEY,))
        run_count = count_table("research_strategy_runs", "source_key = ?", (TEST_SOURCE_KEY,))
        if signal_count != EXPECTED_SIGNALS or run_count != 1:
            print(f"Result: FAILED - expected {EXPECTED_SIGNALS} signals and 1 run, got {signal_count}/{run_count}.")
            return 1

        outcome_result = run_command(
            "Evaluate replay outcomes",
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
        if outcome_result.returncode != 0:
            print("Result: FAILED - replay outcome evaluator failed.")
            return 1
        outcomes = outcome_count()
        breakdown = outcome_breakdown()
        if outcomes != EXPECTED_OUTCOMES or breakdown.get("WIN", 0) != EXPECTED_OUTCOMES:
            print(f"Result: FAILED - expected {EXPECTED_OUTCOMES} WIN outcomes, got {outcomes} outcomes and {breakdown}.")
            return 1

        cleanup()
        after_candles = count_table("research_market_candles", "source_key = ?", (TEST_SOURCE_KEY,))
        after_signals = count_table("research_signals", "source_key = ?", (TEST_SOURCE_KEY,))
        after_outcomes = outcome_count()
        after_runs = count_table("research_strategy_runs", "source_key = ?", (TEST_SOURCE_KEY,))

        print("-" * 72)
        print("Verification")
        print("-" * 72)
        print(f"Candles imported: {candle_count}")
        print(f"Signals inserted: {signal_count}")
        print(f"Outcomes inserted: {outcomes}")
        print(f"Outcome breakdown: {breakdown}")
        print(f"Rows after cleanup - candles/signals/outcomes/runs: {after_candles}/{after_signals}/{after_outcomes}/{after_runs}")

        if after_candles != 0 or after_signals != 0 or after_outcomes != 0 or after_runs != 0:
            print("Result: FAILED - cleanup did not remove dummy pipeline rows.")
            return 1

        print("Result: PASSED")
        print("End-to-end replay research pipeline works on dummy data.")
        print("No native trades were changed.")
        print("=" * 72)
        return 0
    finally:
        cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
