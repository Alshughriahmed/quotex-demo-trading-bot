from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys


BOT_DIR = Path(__file__).resolve().parents[1]
if str(BOT_DIR) not in sys.path:
    sys.path.insert(0, str(BOT_DIR))

from market_sources import MarketCandle, validate_candle, validate_candle_sequence


def valid_sample_candles() -> list[MarketCandle]:
    start = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    return [
        MarketCandle(
            source_key="dummy_read_only",
            asset="EUR/USD",
            timeframe_seconds=60,
            candle_time=start,
            open=1.1000,
            high=1.1010,
            low=1.0990,
            close=1.1005,
            volume=None,
            is_closed=True,
        ),
        MarketCandle(
            source_key="dummy_read_only",
            asset="EUR/USD",
            timeframe_seconds=60,
            candle_time=start + timedelta(seconds=60),
            open=1.1005,
            high=1.1020,
            low=1.1000,
            close=1.1015,
            volume=None,
            is_closed=True,
        ),
        MarketCandle(
            source_key="dummy_read_only",
            asset="EUR/USD",
            timeframe_seconds=60,
            candle_time=start + timedelta(seconds=120),
            open=1.1015,
            high=1.1025,
            low=1.1010,
            close=1.1020,
            volume=None,
            is_closed=True,
        ),
    ]


def invalid_sample_candles() -> list[MarketCandle]:
    start = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    return [
        MarketCandle(
            source_key="dummy_read_only",
            asset="EUR/USD",
            timeframe_seconds=60,
            candle_time=start,
            open=1.1000,
            high=1.0990,
            low=1.1010,
            close=1.1005,
            volume=None,
            is_closed=True,
        ),
        MarketCandle(
            source_key="dummy_read_only",
            asset="EUR/USD",
            timeframe_seconds=60,
            candle_time=start,
            open=1.1005,
            high=1.1020,
            low=1.1000,
            close=1.1015,
            volume=None,
            is_closed=True,
        ),
    ]


def main() -> int:
    print("=" * 72)
    print("QTB market source contract check")
    print("=" * 72)
    print("This uses dummy candle data only.")
    print("It does not connect to a broker, does not start the bot, and does not trade.")

    valid_candles = valid_sample_candles()
    valid_issues = validate_candle_sequence(valid_candles)
    print()
    print("Valid sample:")
    print(f"- Candles: {len(valid_candles)}")
    print(f"- Issues: {len(valid_issues)}")
    if valid_issues:
        for issue in valid_issues:
            print(f"  issue: {issue}")
        print("Result: FAILED - valid sample was rejected.")
        return 1

    invalid_candles = invalid_sample_candles()
    invalid_issues = validate_candle_sequence(invalid_candles)
    single_invalid_issues = validate_candle(invalid_candles[0])
    print()
    print("Invalid sample:")
    print(f"- Candles: {len(invalid_candles)}")
    print(f"- Sequence issues detected: {len(invalid_issues)}")
    print(f"- First-candle issues detected: {len(single_invalid_issues)}")
    if not invalid_issues or not single_invalid_issues:
        print("Result: FAILED - invalid sample was not rejected.")
        return 1

    print()
    print("Result: PASSED")
    print("Market source candle contract validation is working on dummy data.")
    print("No secrets were printed and no native trades were changed.")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
