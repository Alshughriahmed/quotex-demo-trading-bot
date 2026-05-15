from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from sweep_strategy import SweepRow, run_sweep  # noqa: E402
from backtest_strategy import load_candles  # noqa: E402
from experiment_manifest import build_manifest  # noqa: E402


@dataclass(slots=True)
class PortfolioRow:
    rank: int
    duration_seconds: int
    candle_seconds: int
    horizon_candles: int
    drop_open_candle: bool
    min_confidence: int
    lookback: int
    step: int
    files_tested: int
    total_signals: int
    wins: int
    losses: int
    draws: int
    no_trade_windows: int
    closed_trades: int
    win_rate_excluding_draws: float
    win_rate_including_draws: float
    loss_rate: float
    max_consecutive_losses: int
    max_drawdown_units: int
    final_equity_units: int
    average_score: float
    worst_file_score: float
    consistency_score: float


def collect_input_files(paths: list[Path]) -> list[Path]:
    files: list[Path] = []
    for path in paths:
        if path.is_dir():
            files.extend(sorted(path.glob("*.json")))
            files.extend(sorted(path.glob("*.csv")))
        else:
            files.append(path)
    return sorted(set(files))


def combo_key(row: SweepRow) -> tuple[int, int, bool, int, int, int]:
    return (
        row.duration_seconds,
        row.candle_seconds,
        row.drop_open_candle,
        row.min_confidence,
        row.lookback,
        row.step,
    )


def aggregate_rows(rows_by_combo: dict[tuple[int, int, bool, int, int, int], list[SweepRow]]) -> list[PortfolioRow]:
    portfolio_rows: list[PortfolioRow] = []
    for key, rows in rows_by_combo.items():
        duration, candle_seconds, drop_open_candle, min_confidence, lookback, step = key
        wins = sum(row.wins for row in rows)
        losses = sum(row.losses for row in rows)
        draws = sum(row.draws for row in rows)
        no_trade_windows = sum(row.no_trade_windows for row in rows)
        total_signals = sum(row.total_signals for row in rows)
        closed_trades = sum(row.closed_trades for row in rows)
        win_rate = (wins / closed_trades * 100) if closed_trades else 0.0
        loss_rate = (losses / closed_trades * 100) if closed_trades else 0.0
        total_with_draws = wins + losses + draws
        win_rate_with_draws = (wins / total_with_draws * 100) if total_with_draws else 0.0
        scores = [row.score for row in rows]
        average_score = sum(scores) / len(scores) if scores else 0.0
        worst_score = min(scores) if scores else 0.0
        consistency_score = round((average_score * 0.7) + (worst_score * 0.3), 4)
        horizon_values = {row.horizon_candles for row in rows}
        horizon_candles = min(horizon_values) if horizon_values else 0
        portfolio_rows.append(
            PortfolioRow(
                rank=0,
                duration_seconds=duration,
                candle_seconds=candle_seconds,
                horizon_candles=horizon_candles,
                drop_open_candle=drop_open_candle,
                min_confidence=min_confidence,
                lookback=lookback,
                step=step,
                files_tested=len(rows),
                total_signals=total_signals,
                wins=wins,
                losses=losses,
                draws=draws,
                no_trade_windows=no_trade_windows,
                closed_trades=closed_trades,
                win_rate_excluding_draws=round(win_rate, 4),
                win_rate_including_draws=round(win_rate_with_draws, 4),
                loss_rate=round(loss_rate, 4),
                max_consecutive_losses=max((row.max_consecutive_losses for row in rows), default=0),
                max_drawdown_units=max((row.max_drawdown_units for row in rows), default=0),
                final_equity_units=sum(row.final_equity_units for row in rows),
                average_score=round(average_score, 4),
                worst_file_score=round(worst_score, 4),
                consistency_score=consistency_score,
            )
        )
    portfolio_rows.sort(
        key=lambda row: (
            row.consistency_score,
            row.worst_file_score,
            row.win_rate_excluding_draws,
            row.final_equity_units,
            -row.max_drawdown_units,
            -row.max_consecutive_losses,
            row.closed_trades,
            -row.losses,
        ),
        reverse=True,
    )
    for index, row in enumerate(portfolio_rows, start=1):
        row.rank = index
    return portfolio_rows


def run_portfolio_sweep(
    files: list[Path],
    durations: list[int],
    min_confidences: list[int],
    lookbacks: list[int],
    steps: list[int],
    candle_seconds: int = 60,
    drop_open_candle: bool = True,
) -> list[PortfolioRow]:
    rows_by_combo: dict[tuple[int, int, bool, int, int, int], list[SweepRow]] = {}
    for file_path in files:
        candles = load_candles(file_path)
        asset = file_path.stem.upper()
        rows = run_sweep(
            candles=candles,
            asset=asset,
            durations=durations,
            min_confidences=min_confidences,
            lookbacks=lookbacks,
            steps=steps,
            candle_seconds=candle_seconds,
            drop_open_candle=drop_open_candle,
        )
        for row in rows:
            rows_by_combo.setdefault(combo_key(row), []).append(row)
    return aggregate_rows(rows_by_combo)


def print_table(rows: list[PortfolioRow], limit: int) -> None:
    print("Portfolio parameter sweep")
    print("=========================")
    if not rows:
        print("No valid combinations were tested.")
        return
    header = "rank | duration | candle_s | horizon | min_conf | lookback | files | trades | wins | losses | win_rate | max_loss_streak | max_dd | consistency"
    print(header)
    print("-" * len(header))
    for row in rows[:limit]:
        print(
            f"{row.rank:>4} | "
            f"{row.duration_seconds:>8} | "
            f"{row.candle_seconds:>8} | "
            f"{row.horizon_candles:>7} | "
            f"{row.min_confidence:>8} | "
            f"{row.lookback:>8} | "
            f"{row.files_tested:>5} | "
            f"{row.closed_trades:>6} | "
            f"{row.wins:>4} | "
            f"{row.losses:>6} | "
            f"{row.win_rate_excluding_draws:>8.2f}% | "
            f"{row.max_consecutive_losses:>15} | "
            f"{row.max_drawdown_units:>6} | "
            f"{row.consistency_score:>11.2f}"
        )


def write_csv(path: Path, rows: list[PortfolioRow]) -> None:
    if not rows:
        path.write_text("rank\n", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(asdict(rows[0]).keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))


def write_json(path: Path, rows: list[PortfolioRow], settings: dict[str, Any]) -> None:
    payload = {
        "settings": settings,
        "results": [asdict(row) for row in rows],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_manifest(path: Path, command: list[str], input_files: list[Path], outputs: list[Path]) -> None:
    if not outputs:
        raise ValueError("--manifest-out requires at least one output artifact such as --json-out or --csv-out")
    manifest = build_manifest(
        root=ROOT,
        command=command,
        inputs=input_files,
        outputs=outputs,
        note="DEMO-only offline portfolio sweep experiment.",
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_ints(values: list[str]) -> list[int]:
    return [int(value) for value in values]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run parameter sweeps across multiple candle files.")
    parser.add_argument("paths", nargs="+", type=Path, help="Candle files or directories containing .json/.csv candles")
    parser.add_argument("--durations", nargs="+", default=["180"])
    parser.add_argument("--candle-seconds", type=int, default=60, help="Seconds represented by each candle")
    parser.add_argument("--min-confidences", nargs="+", default=["70", "75", "80"])
    parser.add_argument("--lookbacks", nargs="+", default=["60", "90", "120"])
    parser.add_argument("--steps", nargs="+", default=["1"])
    parser.add_argument("--top", type=int, default=10)
    parser.add_argument(
        "--keep-open-candle",
        action="store_true",
        help="Keep the latest candle in strategy windows. Default drops it to match live strategy behavior.",
    )
    parser.add_argument("--csv-out", type=Path)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--manifest-out", type=Path, help="Optional path to write a reproducibility manifest")
    args = parser.parse_args()

    files = collect_input_files(args.paths)
    if not files:
        raise SystemExit("No candle files found.")

    durations = parse_ints(args.durations)
    min_confidences = parse_ints(args.min_confidences)
    lookbacks = parse_ints(args.lookbacks)
    steps = parse_ints(args.steps)
    drop_open_candle = not args.keep_open_candle

    rows = run_portfolio_sweep(
        files=files,
        durations=durations,
        min_confidences=min_confidences,
        lookbacks=lookbacks,
        steps=steps,
        candle_seconds=args.candle_seconds,
        drop_open_candle=drop_open_candle,
    )
    print_table(rows, args.top)

    settings = {
        "files": [str(path) for path in files],
        "durations": durations,
        "candle_seconds": args.candle_seconds,
        "drop_open_candle": drop_open_candle,
        "min_confidences": min_confidences,
        "lookbacks": lookbacks,
        "steps": steps,
    }
    output_artifacts: list[Path] = []
    if args.csv_out:
        write_csv(args.csv_out, rows)
        output_artifacts.append(args.csv_out)
        print(f"CSV portfolio sweep written: {args.csv_out}")
    if args.json_out:
        write_json(args.json_out, rows, settings)
        output_artifacts.append(args.json_out)
        print(f"JSON portfolio sweep written: {args.json_out}")
    if args.manifest_out:
        write_manifest(args.manifest_out, sys.argv, files, output_artifacts)
        print(f"Experiment manifest written: {args.manifest_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
