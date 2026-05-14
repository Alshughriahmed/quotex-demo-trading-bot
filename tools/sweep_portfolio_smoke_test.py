from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


def make_sample_candles(count: int, start: float, first_step: float, second_step: float) -> list[dict[str, float]]:
    candles: list[dict[str, float]] = []
    price = start
    midpoint = count // 2
    for index in range(count):
        step = first_step if index < midpoint else second_step
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
        data_dir = tmp / "candles"
        data_dir.mkdir()
        (data_dir / "eurusd.json").write_text(
            json.dumps(make_sample_candles(180, 1.0, 0.0002, -0.00016)),
            encoding="utf-8",
        )
        (data_dir / "gbpusd.json").write_text(
            json.dumps(make_sample_candles(180, 1.2, 0.00018, -0.00014)),
            encoding="utf-8",
        )
        csv_report = tmp / "portfolio.csv"
        json_report = tmp / "portfolio.json"

        completed = subprocess.run(
            [
                sys.executable,
                str(root / "tools" / "sweep_portfolio.py"),
                str(data_dir),
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
            "Portfolio parameter sweep",
            "rank | duration",
            "CSV portfolio sweep written:",
            "JSON portfolio sweep written:",
        ]
        missing = [item for item in required if item not in output]
        if missing:
            raise AssertionError(f"Portfolio sweep output missing expected fields: {missing}\n{output}")
        if not csv_report.exists():
            raise AssertionError("Portfolio sweep CSV was not created")
        if not json_report.exists():
            raise AssertionError("Portfolio sweep JSON was not created")
        data = json.loads(json_report.read_text(encoding="utf-8"))
        if "settings" not in data or "results" not in data:
            raise AssertionError("Portfolio sweep JSON missing settings or results")
        if not data["results"]:
            raise AssertionError("Portfolio sweep produced no results")
        if data["results"][0].get("files_tested", 0) < 1:
            raise AssertionError("Portfolio sweep did not record tested files")

    print("Portfolio sweep smoke test passed.")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
