from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        sweep_path = tmp / "portfolio_sweep.json"
        report_path = tmp / "strategy_lab.md"
        payload = {
            "settings": {
                "files": ["eurusd.json", "gbpusd.json"],
                "durations": [180],
                "min_confidences": [70, 75],
                "lookbacks": [60, 90],
                "steps": [3],
            },
            "results": [
                {
                    "rank": 1,
                    "duration_seconds": 180,
                    "min_confidence": 70,
                    "lookback": 90,
                    "step": 3,
                    "files_tested": 2,
                    "total_signals": 40,
                    "wins": 28,
                    "losses": 12,
                    "draws": 0,
                    "no_trade_windows": 20,
                    "closed_trades": 40,
                    "win_rate_excluding_draws": 70.0,
                    "win_rate_including_draws": 70.0,
                    "average_score": 60.0,
                    "worst_file_score": 45.0,
                    "consistency_score": 55.5,
                },
                {
                    "rank": 2,
                    "duration_seconds": 180,
                    "min_confidence": 75,
                    "lookback": 60,
                    "step": 3,
                    "files_tested": 2,
                    "total_signals": 15,
                    "wins": 8,
                    "losses": 7,
                    "draws": 0,
                    "no_trade_windows": 30,
                    "closed_trades": 15,
                    "win_rate_excluding_draws": 53.3333,
                    "win_rate_including_draws": 53.3333,
                    "average_score": 20.0,
                    "worst_file_score": -5.0,
                    "consistency_score": 12.5,
                },
            ],
        }
        sweep_path.write_text(json.dumps(payload), encoding="utf-8")

        completed = subprocess.run(
            [
                sys.executable,
                str(root / "tools" / "strategy_lab.py"),
                str(sweep_path),
                "--top",
                "2",
                "--markdown-out",
                str(report_path),
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        if completed.returncode != 0:
            print(completed.stdout)
            print(completed.stderr, file=sys.stderr)
            return completed.returncode

        output = completed.stdout
        required = [
            "# Strategy Lab Report",
            "Top candidates",
            "PROMISING",
            "Recommended next action",
            "Markdown strategy lab report written:",
        ]
        missing = [item for item in required if item not in output]
        if missing:
            raise AssertionError(f"Strategy lab output missing expected fields: {missing}\n{output}")
        if not report_path.exists():
            raise AssertionError("Strategy lab markdown report was not created")
        if "Safety note" not in report_path.read_text(encoding="utf-8"):
            raise AssertionError("Strategy lab report missing safety note")

    print("Strategy lab smoke test passed.")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
