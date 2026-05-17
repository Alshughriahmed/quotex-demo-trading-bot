from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

BOT_DIR = Path(__file__).resolve().parents[1]
if str(BOT_DIR) not in sys.path:
    sys.path.insert(0, str(BOT_DIR))

from research_filters import evaluate_research_candidate, filter_summary


def main() -> int:
    print("=" * 72)
    print("QTB research candidate filter check")
    print("=" * 72)
    print("This checks the research-only filter. It does not trade and does not modify native trades.")

    summary = filter_summary()
    print(f"Filter: {summary['name']}")
    print(f"Version: {summary['version']}")
    print("Bad assets:", ", ".join(summary["bad_assets"]))
    print("Bad UTC hours:", ", ".join(summary["bad_utc_hours"]))
    print("CALL allowed assets:", ", ".join(summary["call_allowed_assets"]))

    samples = [
        ("USD/CAD", "CALL", "15", True),
        ("USD/JPY", "CALL", "00", True),
        ("USD/PKR", "PUT", "19", True),
        ("NZD/USD", "PUT", "20", True),
        ("EUR/USD", "CALL", "15", False),
        ("USD/CAD", "CALL", "12", False),
        ("GBP/USD", "CALL", "15", False),
        ("GBP/USD", "PUT", "15", True),
    ]

    print("-" * 72)
    print("Sample decisions")
    print("-" * 72)
    ok = True
    for asset, direction, hour, expected in samples:
        decision = evaluate_research_candidate(asset, direction, hour)
        result = "PASS" if decision.allowed == expected else "FAIL"
        if result == "FAIL":
            ok = False
        print(f"{asset} {direction} hour={hour} -> allowed={decision.allowed} reason={decision.reason} [{result}]")

    print("-" * 72)
    print("Decision")
    print("-" * 72)
    if ok:
        print("Result: PASSED")
        print("The research candidate filter behaves as expected.")
    else:
        print("Result: FAILED")
        return 1
    print("Important: this is still research-only and not a live trading permission.")
    print(f"Checked at UTC: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())