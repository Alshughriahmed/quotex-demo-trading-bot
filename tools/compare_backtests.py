from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class ReportRow:
    name: str
    source: str
    asset: str
    duration_seconds: int
    min_confidence: int
    lookback: int
    step: int
    total_signals: int
    wins: int
    losses: int
    draws: int
    no_trade_windows: int
    closed_trades: int
    win_rate_excluding_draws: float
    win_rate_including_draws: float

    @property
    def score(self) -> float:
        """Simple ranking score that rewards win rate and enough closed trades."""
        trade_factor = min(1.0, self.closed_trades / 30) if self.closed_trades else 0.0
        return round(self.win_rate_excluding_draws * trade_factor, 4)


def load_report(path: Path) -> ReportRow:
    data = json.loads(path.read_text(encoding="utf-8"))
    settings = data.get("settings") or {}
    summary = data.get("summary") or {}
    return ReportRow(
        name=path.stem,
        source=str(settings.get("source", "")),
        asset=str(settings.get("asset", "")),
        duration_seconds=int(settings.get("duration_seconds", 0) or 0),
        min_confidence=int(settings.get("min_confidence", 0) or 0),
        lookback=int(settings.get("lookback", 0) or 0),
        step=int(settings.get("step", 0) or 0),
        total_signals=int(summary.get("total_signals", 0) or 0),
        wins=int(summary.get("wins", 0) or 0),
        losses=int(summary.get("losses", 0) or 0),
        draws=int(summary.get("draws", 0) or 0),
        no_trade_windows=int(summary.get("no_trade_windows", 0) or 0),
        closed_trades=int(summary.get("closed_trades", 0) or 0),
        win_rate_excluding_draws=float(summary.get("win_rate_excluding_draws", 0.0) or 0.0),
        win_rate_including_draws=float(summary.get("win_rate_including_draws", 0.0) or 0.0),
    )


def collect_reports(paths: list[Path]) -> list[ReportRow]:
    reports: list[ReportRow] = []
    for path in paths:
        if path.is_dir():
            for item in sorted(path.glob("*.json")):
                reports.append(load_report(item))
        else:
            reports.append(load_report(path))
    return reports


def print_table(rows: list[ReportRow]) -> None:
    print("Backtest comparison")
    print("===================")
    if not rows:
        print("No reports found.")
        return

    header = (
        "rank | report | asset | trades | wins | losses | draws | "
        "win_rate | no_trade | score"
    )
    print(header)
    print("-" * len(header))
    for index, row in enumerate(rows, start=1):
        print(
            f"{index:>4} | "
            f"{row.name} | "
            f"{row.asset or '-'} | "
            f"{row.closed_trades:>6} | "
            f"{row.wins:>4} | "
            f"{row.losses:>6} | "
            f"{row.draws:>5} | "
            f"{row.win_rate_excluding_draws:>8.2f}% | "
            f"{row.no_trade_windows:>8} | "
            f"{row.score:>6.2f}"
        )


def write_csv(path: Path, rows: list[ReportRow]) -> None:
    fieldnames = [
        "rank",
        "name",
        "source",
        "asset",
        "duration_seconds",
        "min_confidence",
        "lookback",
        "step",
        "total_signals",
        "wins",
        "losses",
        "draws",
        "no_trade_windows",
        "closed_trades",
        "win_rate_excluding_draws",
        "win_rate_including_draws",
        "score",
    ]
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for index, row in enumerate(rows, start=1):
            writer.writerow({"rank": index, **row_to_dict(row), "score": row.score})


def row_to_dict(row: ReportRow) -> dict[str, Any]:
    return {
        "name": row.name,
        "source": row.source,
        "asset": row.asset,
        "duration_seconds": row.duration_seconds,
        "min_confidence": row.min_confidence,
        "lookback": row.lookback,
        "step": row.step,
        "total_signals": row.total_signals,
        "wins": row.wins,
        "losses": row.losses,
        "draws": row.draws,
        "no_trade_windows": row.no_trade_windows,
        "closed_trades": row.closed_trades,
        "win_rate_excluding_draws": row.win_rate_excluding_draws,
        "win_rate_including_draws": row.win_rate_including_draws,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare JSON reports produced by backtest_strategy.py")
    parser.add_argument("paths", nargs="+", type=Path, help="JSON report files or directories containing reports")
    parser.add_argument("--csv-out", type=Path, help="Optional CSV output for the comparison table")
    args = parser.parse_args()

    rows = collect_reports(args.paths)
    rows.sort(key=lambda row: (row.score, row.win_rate_excluding_draws, row.closed_trades), reverse=True)
    print_table(rows)
    if args.csv_out:
        write_csv(args.csv_out, rows)
        print(f"CSV comparison written: {args.csv_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
