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
        manifest_path = tmp / "portfolio_sweep_manifest.json"
        report_path = tmp / "strategy_lab.md"
        payload = {
            "settings": {
                "files": ["eurusd.json", "gbpusd.json"],
                "durations": [180],
                "candle_seconds": 60,
                "drop_open_candle": True,
                "min_confidences": [70, 75, 80],
                "lookbacks": [60, 90],
                "steps": [3],
            },
            "results": [
                {
                    "rank": 1,
                    "duration_seconds": 180,
                    "candle_seconds": 60,
                    "horizon_candles": 3,
                    "drop_open_candle": True,
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
                    "loss_rate": 30.0,
                    "max_consecutive_losses": 3,
                    "max_drawdown_units": 5,
                    "final_equity_units": 16,
                    "average_score": 60.0,
                    "worst_file_score": 45.0,
                    "consistency_score": 55.5,
                },
                {
                    "rank": 2,
                    "duration_seconds": 180,
                    "candle_seconds": 60,
                    "horizon_candles": 3,
                    "drop_open_candle": True,
                    "min_confidence": 75,
                    "lookback": 60,
                    "step": 3,
                    "files_tested": 2,
                    "total_signals": 40,
                    "wins": 30,
                    "losses": 10,
                    "draws": 0,
                    "no_trade_windows": 30,
                    "closed_trades": 40,
                    "win_rate_excluding_draws": 75.0,
                    "win_rate_including_draws": 75.0,
                    "loss_rate": 25.0,
                    "max_consecutive_losses": 8,
                    "max_drawdown_units": 12,
                    "final_equity_units": 20,
                    "average_score": 50.0,
                    "worst_file_score": 25.0,
                    "consistency_score": 45.0,
                },
                {
                    "rank": 3,
                    "duration_seconds": 180,
                    "candle_seconds": 60,
                    "horizon_candles": 3,
                    "drop_open_candle": True,
                    "min_confidence": 80,
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
                    "loss_rate": 46.6667,
                    "max_consecutive_losses": 4,
                    "max_drawdown_units": 6,
                    "final_equity_units": 1,
                    "average_score": 20.0,
                    "worst_file_score": -5.0,
                    "consistency_score": 12.5,
                },
            ],
        }
        manifest = {
            "created_at_utc": "2026-05-15T04:00:00+00:00",
            "repo_commit": "abc123",
            "command": ["python", "tools/sweep_portfolio.py", "data/candles", "--manifest-out", str(manifest_path)],
            "inputs": [
                {"path": "eurusd.json", "size_bytes": 100, "sha256": "a" * 64},
                {"path": "gbpusd.json", "size_bytes": 100, "sha256": "b" * 64},
            ],
            "outputs": [
                {"path": "portfolio_sweep.json", "size_bytes": 100, "sha256": "c" * 64},
            ],
            "safety": {
                "demo_only": True,
                "profitability_warning": "Backtest and sweep artifacts are engineering evidence only; they do not prove profitability or enable real-money trading.",
            },
        }
        sweep_path.write_text(json.dumps(payload), encoding="utf-8")
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        completed = subprocess.run(
            [
                sys.executable,
                str(root / "tools" / "strategy_lab.py"),
                str(sweep_path),
                "--top",
                "3",
                "--manifest",
                str(manifest_path),
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
            "Experiment manifest",
            "Manifest path:",
            "Repository commit: abc123",
            "DEMO-only recorded: True",
            "Candle seconds",
            "Top candidates",
            "PROMISING",
            "RISKY",
            "Max loss streak",
            "Max DD",
            "drawdown too high",
            "Recommended next action",
            "Markdown strategy lab report written:",
        ]
        missing = [item for item in required if item not in output]
        if missing:
            raise AssertionError(f"Strategy lab output missing expected fields: {missing}\n{output}")
        if not report_path.exists():
            raise AssertionError("Strategy lab markdown report was not created")
        report = report_path.read_text(encoding="utf-8")
        for item in ("Safety note", "Loss rate", "Final equity", "This project remains DEMO-only", "Experiment manifest"):
            if item not in report:
                raise AssertionError(f"Strategy lab report missing {item!r}")

    print("Strategy lab smoke test passed.")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
