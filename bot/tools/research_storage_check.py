from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
import sys


BOT_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BOT_DIR / "data.db"
if str(BOT_DIR) not in sys.path:
    sys.path.insert(0, str(BOT_DIR))

from market_sources import MarketCandle
from research import store_market_candles

TEST_SOURCE_KEY = "dummy_storage_check"


def sample_candles() -> list[MarketCandle]:
    start = datetime(2026, 1, 1, 15, 0, tzinfo=timezone.utc)
    return [
        MarketCandle(TEST_SOURCE_KEY, "EUR/USD", 60, start, 1.1000, 1.1010, 1.0990, 1.1005),
        MarketCandle(TEST_SOURCE_KEY, "EUR/USD", 60, start + timedelta(seconds=60), 1.1005, 1.1015, 1.1000, 1.1010),
        MarketCandle(TEST_SOURCE_KEY, "EUR/USD", 60, start + timedelta(seconds=120), 1.1010, 1.1020, 1.1005, 1.1018),
    ]


def count_test_rows() -> int:
    with sqlite3.connect(DB_PATH) as db:
        row = db.execute(
            "SELECT COUNT(*) FROM research_market_candles WHERE source_key = ?",
            (TEST_SOURCE_KEY,),
        ).fetchone()
        return int(row[0] or 0)


def cleanup_test_rows() -> None:
    with sqlite3.connect(DB_PATH) as db:
        db.execute("DELETE FROM research_market_candles WHERE source_key = ?", (TEST_SOURCE_KEY,))
        db.commit()


def main() -> int:
    print("=" * 72)
    print("QTB research candle storage check")
    print("=" * 72)
    print("This stores dummy candles briefly, verifies them, then removes them.")
    print("It does not start the bot, does not trade, and does not print secrets.")
    print(f"Database: {DB_PATH}")

    if not DB_PATH.exists():
        print("Database not found. Run init_signal_research_tables first.")
        return 1

    cleanup_test_rows()
    before = count_test_rows()
    if before != 0:
        print("Could not clean old dummy rows before test.")
        return 1

    candles = sample_candles()
    stored = store_market_candles(DB_PATH, candles)
    after_insert = count_test_rows()

    cleanup_test_rows()
    after_cleanup = count_test_rows()

    print(f"Dummy candles requested: {len(candles)}")
    print(f"Store function count: {stored}")
    print(f"Rows after insert: {after_insert}")
    print(f"Rows after cleanup: {after_cleanup}")

    if stored != len(candles) or after_insert != len(candles) or after_cleanup != 0:
        print("Result: FAILED")
        return 1

    print("Result: PASSED")
    print("Validated dummy candles can be stored and cleaned from research_market_candles.")
    print("No native trades were changed.")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
