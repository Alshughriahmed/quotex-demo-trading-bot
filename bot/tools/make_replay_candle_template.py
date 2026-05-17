from __future__ import annotations

from pathlib import Path


BOT_DIR = Path(__file__).resolve().parents[1]
INBOX_DIR = BOT_DIR / "external_inputs"
TEMPLATE_PATH = INBOX_DIR / "replay_candles_template.csv"

TEMPLATE_CONTENT = """source_key,asset,timeframe_seconds,candle_time,open,high,low,close,volume,is_closed
replay_csv,EUR/USD,60,2026-01-01T12:00:00Z,1.1000,1.1010,1.0990,1.1005,,true
replay_csv,EUR/USD,60,2026-01-01T12:01:00Z,1.1005,1.1015,1.1000,1.1010,,true
replay_csv,EUR/USD,60,2026-01-01T12:02:00Z,1.1010,1.1020,1.1005,1.1018,,true
"""

NOTES = """# QTB Replay Candle CSV Format

Put historical candle CSV files in this folder, then run import_replay_candles.

Required columns:
- asset
- timeframe_seconds
- candle_time
- open
- high
- low
- close

Optional columns:
- source_key
- volume
- is_closed

Rules:
- candle_time should be ISO format, preferably UTC with Z, like 2026-01-01T12:00:00Z
- OHLC prices must be positive.
- high must be >= open, low, close.
- low must be <= open, high, close.
- candles for the same source_key + asset + timeframe must be strictly increasing by time.
- This is for replay research only. It does not execute trades.
"""


def main() -> int:
    print("=" * 72)
    print("QTB replay candle CSV template")
    print("=" * 72)
    print("This creates a template file only. It does not import data or trade.")

    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    TEMPLATE_PATH.write_text(TEMPLATE_CONTENT, encoding="utf-8")
    notes_path = INBOX_DIR / "REPLAY_CANDLE_CSV_FORMAT.txt"
    notes_path.write_text(NOTES, encoding="utf-8")

    print(f"Template created: {TEMPLATE_PATH}")
    print(f"Notes created: {notes_path}")
    print("Use real historical candle data with the same columns when available.")
    print("No secrets were printed and no native trades were changed.")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
