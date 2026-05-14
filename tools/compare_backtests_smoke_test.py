from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


def write_report(path: Path, name: str, wins: int, losses: int, draws: int, no_trade: int) -> None:
    closed = wins + losses
    total = wins + losses + draws
    payload = {
        "settings": {
            "source": f"{name}.json",
            "asset": "TEST/COMPARE",
            "duration_seconds": 180,
            "min_confidence": 75,
            "lookback": 90,
            "step": 1,
            "candles": 200,
        },
        "summary": {
            "total_signals": total,
            "wins": wins,
            "losses": losses,
            "draws": draws,
            "no_trade_windows": no_trade,
            "closed_trades": closed,
            "win_rate_excluding_draws": round((wins / closed) * 100, 4) if closed else 0,
            "win_rate_including_draws": round((wins / total) * 100, 4) if total else 0,
        },
        "trades": [],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        write_report(tmp / "weak.json", "weak", wins=4, losses=6, draws=0, no_trade=20)
        write_report(tmp / "strong.json", "strong", wins=24, losses=6, draws=0, no_trade=10)
        csv_path = tmp / "comparison.csv"

        completed = subprocess.run(
            [
                sys.executable,
                str(root / "tools" / "compare_backtests.py"),
                str(tmp),
                "--csv-out",
                str(csv_path),
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
        required = ["Backtest comparison", "rank | report", "strong", "weak", "CSV comparison written:"]
        missing = [item for item in required if item not in output]
        if missing:
            raise AssertionError(f"Comparison output missing expected fields: {missing}\n{output}")
        if not csv_path.exists():
            raise AssertionError("Comparison CSV was not created")
        csv_text = csv_path.read_text(encoding="utf-8")
        if "score" not in csv_text.splitlines()[0]:
            raise AssertionError("Comparison CSV header missing score")

    print("Backtest comparison smoke test passed.")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
