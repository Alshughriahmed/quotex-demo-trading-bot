from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


def make_sample_candles(count: int = 140) -> list[dict[str, float]]:
    candles: list[dict[str, float]] = []
    price = 1.0
    for index in range(count):
        if index < 70:
            step = 0.00022
        else:
            step = -0.00018
        open_price = price
        close_price = price + step
        candles.append(
            {
                "time": float(index),
                "open": round(open_price, 8),
                "high": round(max(open_price, close_price) + 0.00005, 8),
                "low": round(min(open_price, close_price) - 0.00005, 8),
                "close": round(close_price, 8),
            }
        )
        price = close_price + (0.00002 if step > 0 else -0.00002)
    return candles


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        candles_path = tmp / "sample_candles.json"
        json_report = tmp / "report.json"
        csv_report = tmp / "trades.csv"
        manifest_report = tmp / "manifest.json"
        candles_path.write_text(json.dumps(make_sample_candles()), encoding="utf-8")

        completed = subprocess.run(
            [
                sys.executable,
                str(root / "tools" / "backtest_strategy.py"),
                str(candles_path),
                "--asset",
                "TEST/SMOKE",
                "--duration",
                "180",
                "--candle-seconds",
                "60",
                "--min-confidence",
                "65",
                "--lookback",
                "80",
                "--step",
                "3",
                "--json-out",
                str(json_report),
                "--csv-out",
                str(csv_report),
                "--manifest-out",
                str(manifest_report),
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
            "Offline strategy backtest",
            "Signals:",
            "Wins:",
            "Losses:",
            "No-trade windows:",
            "Win rate excluding draws:",
            "Loss rate:",
            "Max consecutive losses:",
            "Max drawdown units:",
            "Final equity units:",
            "JSON report written:",
            "CSV trades written:",
            "Experiment manifest written:",
        ]
        missing = [item for item in required if item not in output]
        if missing:
            raise AssertionError(f"Backtest output missing expected fields: {missing}\n{output}")

        if not json_report.exists():
            raise AssertionError("JSON report was not created")
        if not csv_report.exists():
            raise AssertionError("CSV report was not created")
        if not manifest_report.exists():
            raise AssertionError("Manifest report was not created")

        report = json.loads(json_report.read_text(encoding="utf-8"))
        for key in ("settings", "summary", "trades"):
            if key not in report:
                raise AssertionError(f"JSON report missing key: {key}")
        expected_settings = {
            "candle_seconds": 60,
            "horizon_candles": 3,
            "drop_open_candle": True,
        }
        for key, expected_value in expected_settings.items():
            actual_value = report["settings"].get(key)
            if actual_value != expected_value:
                raise AssertionError(f"Expected settings[{key!r}]={expected_value!r}, got {actual_value!r}")
        expected_summary_keys = [
            "total_signals",
            "loss_rate",
            "max_consecutive_losses",
            "max_drawdown_units",
            "final_equity_units",
        ]
        for key in expected_summary_keys:
            if key not in report["summary"]:
                raise AssertionError(f"JSON summary missing {key}")
        csv_header = csv_report.read_text(encoding="utf-8").splitlines()[0]
        for key in ("outcome", "equity_after_trade", "drawdown_after_trade"):
            if key not in csv_header:
                raise AssertionError(f"CSV report header missing {key}")

        manifest = json.loads(manifest_report.read_text(encoding="utf-8"))
        for key in ("created_at_utc", "repo_commit", "command", "inputs", "outputs", "safety"):
            if key not in manifest:
                raise AssertionError(f"Manifest missing key: {key}")
        if len(manifest["inputs"]) != 1:
            raise AssertionError("Manifest should include the candle input file")
        if len(manifest["outputs"]) != 2:
            raise AssertionError("Manifest should include JSON and CSV output artifacts")
        if manifest["safety"].get("demo_only") is not True:
            raise AssertionError("Manifest should explicitly remain DEMO-only")
        if "does not prove profitability" not in manifest["safety"].get("profitability_warning", ""):
            raise AssertionError("Manifest missing profitability warning")

    print("Backtest smoke test passed.")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
