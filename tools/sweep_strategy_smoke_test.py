from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


def make_sample_candles(count: int = 180) -> list[dict[str, float]]:
    candles: list[dict[str, float]] = []
    price = 1.0
    for index in range(count):
        if index < 90:
            step = 0.0002
        else:
            step = -0.00016
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
        csv_report = tmp / "sweep.csv"
        json_report = tmp / "sweep.json"
        candles_path.write_text(json.dumps(make_sample_candles()), encoding="utf-8")

        completed = subprocess.run(
            [
                sys.executable,
                str(root / "tools" / "sweep_strategy.py"),
                str(candles_path),
                "--asset",
                "TEST/SWEEP",
                "--durations",
                "180",
                "--min-confidences",
                "65",
                "70",
                "--lookbacks",
                "60",
                "90",
                "--steps",
                "3",
                "--top",
                "5",
                "--csv-out",
                str(csv_report),
                "--json-out",
                str(json_report),
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
            "Strategy parameter sweep",
            "rank | duration",
            "CSV sweep written:",
            "JSON sweep written:",
        ]
        missing = [item for item in required if item not in output]
        if missing:
            raise AssertionError(f"Sweep output missing expected fields: {missing}\n{output}")
        if not csv_report.exists():
            raise AssertionError("Sweep CSV was not created")
        if not json_report.exists():
            raise AssertionError("Sweep JSON was not created")
        data = json.loads(json_report.read_text(encoding="utf-8"))
        if "settings" not in data or "results" not in data:
            raise AssertionError("Sweep JSON missing settings or results")
        if not data["results"]:
            raise AssertionError("Sweep produced no results")

    print("Strategy sweep smoke test passed.")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
