from __future__ import annotations

from pathlib import Path

from market_sources import get_market_source_status


BOT_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BOT_DIR / "data.db"


def main() -> int:
    status = get_market_source_status(DB_PATH)
    print("=" * 72)
    print("QTB market source status")
    print("=" * 72)
    print(f"Database: {DB_PATH}")
    print(f"Source key: {status.source_key}")
    print(f"Label: {status.label}")
    print(f"Configured: {status.configured}")
    print(f"Enabled: {status.enabled}")
    print(f"Safe for signal-only: {status.safe_for_signal_only}")
    print(f"Readiness: {status.readiness}")
    print(f"Reason: {status.reason}")
    print("No secrets were inspected or printed.")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
