from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


def make_row(
    *,
    rank: int,
    wins: int,
    losses: int,
    files_tested: int,
    worst: float,
    consistency: float,
    max_consecutive_losses: int,
    max_drawdown_units: int,
    final_equity_units: int,
) -> dict[str, object]:
    closed = wins + losses
    loss_rate = (losses / closed) * 100 if closed else 0
    return {
        "rank": rank,
        "duration_seconds": 180,
        "candle_seconds": 60,
        "horizon_candles": 3,
        "drop_open_candle": True,
        "min_confidence": 70,
        "lookback": 90,
        "step": 3,
        "files_tested": files_tested,
        "total_signals": closed,
        "wins": wins,
        "losses": losses,
        "draws": 0,
        "no_trade_windows": 10,
        "closed_trades": closed,
        "win_rate_excluding_draws": round((wins / closed) * 100, 4) if closed else 0,
        "win_rate_including_draws": round((wins / closed) * 100, 4) if closed else 0,
        "loss_rate": round(loss_rate, 4),
        "max_consecutive_losses": max_consecutive_losses,
        "max_drawdown_units": max_drawdown_units,
        "final_equity_units": final_equity_units,
        "average_score": consistency,
        "worst_file_score": worst,
        "consistency_score": consistency,
    }


def write_report(path: Path, rows: list[dict[str, object]]) -> None:
    max_files = max(int(row.get("files_tested", 0) or 0) for row in rows) if rows else 0
    payload = {
        "settings": {"files": [f"file_{index}.json" for index in range(max_files)]},
        "results": rows,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def run_gate(root: Path, report: Path, *, top_candidates: int = 1) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(root / "tools" / "strategy_acceptance_gate.py"),
            str(report),
            "--top-candidates",
            str(top_candidates),
            "--min-files",
            "2",
            "--min-closed-trades",
            "30",
            "--min-win-rate",
            "60",
            "--min-worst-file-score",
            "1",
            "--min-consistency-score",
            "35",
            "--max-loss-rate",
            "45",
            "--max-consecutive-losses",
            "5",
            "--max-drawdown-units",
            "8",
            "--min-final-equity-units",
            "1",
        ],
        check=False,
        capture_output=True,
        text=True,
    )


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        passing = tmp / "passing.json"
        failing = tmp / "failing.json"
        risky = tmp / "risky.json"
        second_candidate_passes = tmp / "second_candidate_passes.json"

        write_report(
            passing,
            [
                make_row(
                    rank=1,
                    wins=24,
                    losses=10,
                    files_tested=2,
                    worst=12.0,
                    consistency=45.0,
                    max_consecutive_losses=3,
                    max_drawdown_units=5,
                    final_equity_units=14,
                )
            ],
        )
        write_report(
            failing,
            [
                make_row(
                    rank=1,
                    wins=10,
                    losses=20,
                    files_tested=1,
                    worst=-5.0,
                    consistency=10.0,
                    max_consecutive_losses=8,
                    max_drawdown_units=12,
                    final_equity_units=-10,
                )
            ],
        )
        write_report(
            risky,
            [
                make_row(
                    rank=1,
                    wins=30,
                    losses=10,
                    files_tested=3,
                    worst=14.0,
                    consistency=50.0,
                    max_consecutive_losses=7,
                    max_drawdown_units=11,
                    final_equity_units=20,
                )
            ],
        )
        write_report(
            second_candidate_passes,
            [
                make_row(
                    rank=1,
                    wins=12,
                    losses=18,
                    files_tested=2,
                    worst=-4.0,
                    consistency=20.0,
                    max_consecutive_losses=6,
                    max_drawdown_units=9,
                    final_equity_units=-6,
                ),
                make_row(
                    rank=2,
                    wins=24,
                    losses=10,
                    files_tested=2,
                    worst=12.0,
                    consistency=45.0,
                    max_consecutive_losses=3,
                    max_drawdown_units=5,
                    final_equity_units=14,
                ),
            ],
        )

        pass_result = run_gate(root, passing)
        fail_result = run_gate(root, failing)
        risky_result = run_gate(root, risky)
        first_only_result = run_gate(root, second_candidate_passes, top_candidates=1)
        top_two_result = run_gate(root, second_candidate_passes, top_candidates=2)

        if pass_result.returncode != 0:
            print(pass_result.stdout)
            print(pass_result.stderr, file=sys.stderr)
            raise AssertionError("Expected passing report to pass")
        if fail_result.returncode == 0:
            print(fail_result.stdout)
            raise AssertionError("Expected failing report to fail")
        if risky_result.returncode == 0:
            print(risky_result.stdout)
            raise AssertionError("Expected risky report to fail risk rules")
        if first_only_result.returncode == 0:
            print(first_only_result.stdout)
            raise AssertionError("Expected first-only evaluation to fail")
        if top_two_result.returncode != 0:
            print(top_two_result.stdout)
            print(top_two_result.stderr, file=sys.stderr)
            raise AssertionError("Expected top-two evaluation to pass because rank 2 passes")

        if "Decision: PASS" not in pass_result.stdout:
            raise AssertionError(f"Passing output missing PASS decision:\n{pass_result.stdout}")
        if "Decision: FAIL" not in fail_result.stdout:
            raise AssertionError(f"Failing output missing FAIL decision:\n{fail_result.stdout}")
        if "Decision: FAIL" not in risky_result.stdout:
            raise AssertionError(f"Risky output missing FAIL decision:\n{risky_result.stdout}")
        if "minimum files tested" not in fail_result.stdout:
            raise AssertionError("Failing output missing rule details")
        if "maximum consecutive losses" not in risky_result.stdout:
            raise AssertionError("Risky output missing consecutive-loss rule details")
        if "maximum drawdown units" not in risky_result.stdout:
            raise AssertionError("Risky output missing drawdown rule details")
        if "Candidates evaluated: 2" not in top_two_result.stdout:
            raise AssertionError("Top-two output missing evaluated count")
        if "First passing rank: 2" not in top_two_result.stdout:
            raise AssertionError("Top-two output missing first passing rank")

    print("Strategy acceptance gate smoke test passed.")
    print(pass_result.stdout)
    print(fail_result.stdout)
    print(risky_result.stdout)
    print(top_two_result.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
