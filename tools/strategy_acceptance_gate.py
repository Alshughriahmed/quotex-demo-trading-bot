from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class GateRule:
    name: str
    passed: bool
    detail: str


def load_report(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if "results" not in data:
        raise ValueError("Expected a JSON report produced by sweep_portfolio.py")
    return data


def candidate_rows(data: dict[str, Any], top: int) -> list[dict[str, Any]]:
    rows = data.get("results") or []
    if not rows:
        raise ValueError("Report contains no results")
    if top <= 0:
        raise ValueError("--top-candidates must be greater than zero")
    return rows[:top]


def evaluate(row: dict[str, Any], args: argparse.Namespace) -> list[GateRule]:
    files_tested = int(row.get("files_tested", 0) or 0)
    closed_trades = int(row.get("closed_trades", 0) or 0)
    win_rate = float(row.get("win_rate_excluding_draws", 0) or 0)
    worst_file_score = float(row.get("worst_file_score", 0) or 0)
    consistency_score = float(row.get("consistency_score", 0) or 0)
    losses = int(row.get("losses", 0) or 0)
    loss_rate = float(row.get("loss_rate", 0) or 0)
    if loss_rate <= 0 and closed_trades:
        loss_rate = losses / closed_trades * 100
    if not closed_trades:
        loss_rate = 100.0
    max_consecutive_losses = int(row.get("max_consecutive_losses", 0) or 0)
    max_drawdown_units = int(row.get("max_drawdown_units", 0) or 0)
    final_equity_units = int(row.get("final_equity_units", 0) or 0)

    return [
        GateRule(
            "minimum files tested",
            files_tested >= args.min_files,
            f"files_tested={files_tested}, required>={args.min_files}",
        ),
        GateRule(
            "minimum closed trades",
            closed_trades >= args.min_closed_trades,
            f"closed_trades={closed_trades}, required>={args.min_closed_trades}",
        ),
        GateRule(
            "minimum win rate",
            win_rate >= args.min_win_rate,
            f"win_rate={win_rate:.2f}%, required>={args.min_win_rate:.2f}%",
        ),
        GateRule(
            "minimum worst-file score",
            worst_file_score >= args.min_worst_file_score,
            f"worst_file_score={worst_file_score:.2f}, required>={args.min_worst_file_score:.2f}",
        ),
        GateRule(
            "minimum consistency score",
            consistency_score >= args.min_consistency_score,
            f"consistency_score={consistency_score:.2f}, required>={args.min_consistency_score:.2f}",
        ),
        GateRule(
            "maximum loss rate",
            loss_rate <= args.max_loss_rate,
            f"loss_rate={loss_rate:.2f}%, required<={args.max_loss_rate:.2f}%",
        ),
        GateRule(
            "maximum consecutive losses",
            max_consecutive_losses <= args.max_consecutive_losses,
            f"max_consecutive_losses={max_consecutive_losses}, required<={args.max_consecutive_losses}",
        ),
        GateRule(
            "maximum drawdown units",
            max_drawdown_units <= args.max_drawdown_units,
            f"max_drawdown_units={max_drawdown_units}, required<={args.max_drawdown_units}",
        ),
        GateRule(
            "minimum final equity units",
            final_equity_units >= args.min_final_equity_units,
            f"final_equity_units={final_equity_units}, required>={args.min_final_equity_units}",
        ),
    ]


def candidate_passed(rules: list[GateRule]) -> bool:
    return all(rule.passed for rule in rules)


def print_candidate(row: dict[str, Any], rules: list[GateRule]) -> None:
    passed = candidate_passed(rules)
    rank = row.get("rank", "unknown")
    print(f"Candidate rank: {rank}")
    print(f"Decision: {'PASS' if passed else 'FAIL'}")
    print("")
    print("Candidate settings:")
    print(f"  duration_seconds: {row.get('duration_seconds')}")
    print(f"  candle_seconds: {row.get('candle_seconds')}")
    print(f"  horizon_candles: {row.get('horizon_candles')}")
    print(f"  drop_open_candle: {row.get('drop_open_candle')}")
    print(f"  min_confidence: {row.get('min_confidence')}")
    print(f"  lookback: {row.get('lookback')}")
    print(f"  step: {row.get('step')}")
    print("")
    print("Risk metrics:")
    print(f"  loss_rate: {row.get('loss_rate')}")
    print(f"  max_consecutive_losses: {row.get('max_consecutive_losses')}")
    print(f"  max_drawdown_units: {row.get('max_drawdown_units')}")
    print(f"  final_equity_units: {row.get('final_equity_units')}")
    print("")
    print("Rules:")
    for rule in rules:
        icon = "PASS" if rule.passed else "FAIL"
        print(f"  [{icon}] {rule.name}: {rule.detail}")
    print("")


def print_gate_report(evaluated: list[tuple[dict[str, Any], list[GateRule]]]) -> None:
    passing_candidates = [row for row, rules in evaluated if candidate_passed(rules)]
    print("Strategy acceptance gate")
    print("========================")
    print(f"Decision: {'PASS' if passing_candidates else 'FAIL'}")
    print(f"Candidates evaluated: {len(evaluated)}")
    if passing_candidates:
        print(f"First passing rank: {passing_candidates[0].get('rank', 'unknown')}")
    print("")
    for row, rules in evaluated:
        print_candidate(row, rules)
    print("Safety: this gate is an engineering filter only. It does not prove profitability and does not enable real-money trading.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Fail or pass a portfolio sweep result using conservative acceptance rules.")
    parser.add_argument("path", type=Path, help="Path to portfolio sweep JSON produced by sweep_portfolio.py")
    parser.add_argument("--top-candidates", type=int, default=1, help="Number of ranked candidates to evaluate instead of only the first row")
    parser.add_argument("--min-files", type=int, default=2)
    parser.add_argument("--min-closed-trades", type=int, default=30)
    parser.add_argument("--min-win-rate", type=float, default=60.0)
    parser.add_argument("--min-worst-file-score", type=float, default=1.0)
    parser.add_argument("--min-consistency-score", type=float, default=35.0)
    parser.add_argument("--max-loss-rate", type=float, default=45.0)
    parser.add_argument("--max-consecutive-losses", type=int, default=5)
    parser.add_argument("--max-drawdown-units", type=int, default=8)
    parser.add_argument("--min-final-equity-units", type=int, default=1)
    args = parser.parse_args()

    data = load_report(args.path)
    rows = candidate_rows(data, args.top_candidates)
    evaluated = [(row, evaluate(row, args)) for row in rows]
    print_gate_report(evaluated)
    return 0 if any(candidate_passed(rules) for _, rules in evaluated) else 1


if __name__ == "__main__":
    raise SystemExit(main())
