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
            "JSON report written:",
            "CSV trades written:",
        ]
        missing = [item for item in required if item not in output]
        if missing:
            raise AssertionError(f"Backtest output missing expected fields: {missing}\n{output}")

        if not json_report.exists():
            raise AssertionError("JSON report was not created")
        if not csv_report.exists():
            raise AssertionError("CSV report was not created")

        report = json.loads(json_report.read_text(encoding="utf-8"))
        for key in ("settings", "summary", "trades"):
            if key not in report:
                raise AssertionError(f"JSON report missing key: {key}")
        if "total_signals" not in report["summary"]:
            raise AssertionError("JSON summary missing total_signals")
        if "outcome" not in csv_report.read_text(encoding="utf-8").splitlines()[0]:
            raise AssertionError("CSV report header missing outcome")

    print("Backtest smoke test passed.")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
