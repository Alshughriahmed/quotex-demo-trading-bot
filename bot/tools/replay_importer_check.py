from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path


BOT_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BOT_DIR / "data.db"
TEMP_CSV = BOT_DIR / "external_inputs" / "replay_importer_check.csv"
TEST_SOURCE_KEY = "replay_importer_check"

CSV_CONTENT = """source_key,asset,timeframe_seconds,candle_time,open,high,low,close,volume,is_closed
replay_importer_check,EUR/USD,60,2026-01-01T12:00:00Z,1.1000,1.1010,1.0990,1.1005,,true
replay_importer_check,EUR/USD,60,2026-01-01T12:01:00Z,1.1005,1.1015,1.1000,1.1010,,true
replay_importer_check,EUR/USD,60,2026-01-01T12:02:00Z,1.1010,1.1020,1.1005,1.1018,,true
"""


def cleanup() -> None:
    if DB_PATH.exists():
        with sqlite3.connect(DB_PATH) as db:
            db.execute("DELETE FROM research_market_candles WHERE source_key = ?", (TEST_SOURCE_KEY,))
            db.commit()
    try:
        TEMP_CSV.unlink(missing_ok=True)
    except OSError:
        pass


def count_rows() -> int:
    with sqlite3.connect(DB_PATH) as db:
        row = db.execute(
            "SELECT COUNT(*) FROM research_market_candles WHERE source_key = ?",
            (TEST_SOURCE_KEY,),
        ).fetchone()
        return int(row[0] or 0)


def run_importer(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "tools/import_replay_candles.py", str(TEMP_CSV), *args],
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


def main() -> int:
    print("=" * 72)
    print("QTB replay importer smoke check")
    print("=" * 72)
    print("This creates a temporary dummy CSV, dry-runs it, imports it, then cleans it up.")
    print("It does not start the bot, does not connect to a broker, and does not trade.")
    print(f"Database: {DB_PATH}")

    if not DB_PATH.exists():
        print("Database not found. Run init_signal_research_tables first.")
        return 1

    cleanup()
    TEMP_CSV.parent.mkdir(parents=True, exist_ok=True)
    TEMP_CSV.write_text(CSV_CONTENT, encoding="utf-8")

    try:
        dry_run = run_importer()
        print_process_result("Dry run", dry_run)
        if dry_run.returncode != 0:
            print("Result: FAILED - dry run failed.")
            return 1
        if count_rows() != 0:
            print("Result: FAILED - dry run inserted rows.")
            return 1

        import_run = run_importer("--yes")
        print_process_result("Import run", import_run)
        if import_run.returncode != 0:
            print("Result: FAILED - import run failed.")
            return 1

        inserted = count_rows()
        cleanup()
        after_cleanup = count_rows()

        print("-" * 72)
        print("Verification")
        print("-" * 72)
        print(f"Rows after import: {inserted}")
        print(f"Rows after cleanup: {after_cleanup}")

        if inserted != 3 or after_cleanup != 0:
            print("Result: FAILED")
            return 1

        print("Result: PASSED")
        print("Replay candle importer can dry-run, import, and clean dummy candles.")
        print("No native trades were changed.")
        print("=" * 72)
        return 0
    finally:
        cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
