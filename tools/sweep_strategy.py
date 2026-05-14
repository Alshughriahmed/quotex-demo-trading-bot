from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import asdict, dataclass
from itertools import product
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from backtest_strategy import calculate_horizon, load_candles, run_backtest  # noqa: E402


@dataclass(slots=True)
class SweepRow:
    rank: int
    asset: str
    duration_seconds: int
    candle_seconds: int
    horizon_candles: int
    drop_open_candle: bool
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
    loss_rate: float
    max_consecutive_losses: int
    max_drawdown_units: int
    final_equity_units: int
    score: float


def score_result(
    closed_trades: int,
    win_rate: float,
    losses: int,
    no_trade_windows: int,
    max_consecutive_losses: int = 0,
    max_drawdown_units: int = 0,
) -> float:
    """Rank settings for engineering comparison, not profit prediction."""
    trade_factor = min(1.0, closed_trades / 30) if closed_trades else 0.0
    loss_penalty = min(20.0, losses * 0.35)
    silence_penalty = min(10.0, no_trade_windows * 0.02)
    streak_penalty = min(12.0, max_consecutive_losses * 1.5)
    drawdown_penalty = min(12.0, max_drawdown_units * 0.9)
    return round((win_rate * trade_factor) - loss_penalty - silence_penalty - streak_penalty - drawdown_penalty, 4)


def run_sweep(
    candles: list[dict[str, Any]],
    asset: str,
    durations: list[int],
    min_confidences: list[int],
    lookbacks: list[int],
    steps: list[int],
    candle_seconds: int = 60,
    drop_open_candle: bool = True,
) -> list[SweepRow]:
    rows: list[SweepRow] = []
    for duration, min_confidence, lookback, step in product(durations, min_confidences, lookbacks, steps):
        horizon = calculate_horizon(duration, candle_seconds)
        if len(candles) < lookback + horizon + 1:
            continue
        result, _trades = run_backtest(
            candles=candles,
            asset=asset,
            duration_seconds=duration,
            min_confidence=min_confidence,
            lookback=lookback,
            step=step,
            candle_seconds=candle_seconds,
            drop_open_candle=drop_open_candle,
        )
        rows.append(
            SweepRow(
                rank=0,
                asset=asset,
                duration_seconds=duration,
                candle_seconds=candle_seconds,
                horizon_candles=horizon,
                drop_open_candle=drop_open_candle,
                min_confidence=min_confidence,
                lookback=lookback,
                step=step,
                total_signals=result.total_signals,
                wins=result.wins,
                losses=result.losses,
                draws=result.draws,
                no_trade_windows=result.no_trade_windows,
                closed_trades=result.closed_trades,
                win_rate_excluding_draws=round(result.win_rate, 4),
                win_rate_including_draws=round(result.accuracy_with_draws, 4),
                loss_rate=round(result.loss_rate, 4),
                max_consecutive_losses=result.max_consecutive_losses,
                max_drawdown_units=result.max_drawdown_units,
                final_equity_units=result.equity_units,
                score=score_result(
                    result.closed_trades,
                    result.win_rate,
                    result.losses,
                    result.no_trade_windows,
                    result.max_consecutive_losses,
                    result.max_drawdown_units,
                ),
            )
        )
    rows.sort(
        key=lambda row: (
            row.score,
            row.win_rate_excluding_draws,
            row.final_equity_units,
            -row.max_drawdown_units,
            -row.max_consecutive_losses,
            row.closed_trades,
            -row.losses,
        ),
        reverse=True,
    )
    for index, row in enumerate(rows, start=1):
        row.rank = index
    return rows


def print_table(rows: list[SweepRow], limit: int) -> None:
    print("Strategy parameter sweep")
    print("========================")
    if not rows:
        print("No valid combinations were tested.")
        return

    header = "rank | duration | candle_s | horizon | min_conf | lookback | step | trades | wins | losses | win_rate | max_loss_streak | max_dd | score"
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
            f"{row.step:>4} | "
            f"{row.closed_trades:>6} | "
            f"{row.wins:>4} | "
            f"{row.losses:>6} | "
            f"{row.win_rate_excluding_draws:>8.2f}% | "
            f"{row.max_consecutive_losses:>15} | "
            f"{row.max_drawdown_units:>6} | "
            f"{row.score:>6.2f}"
        )


def write_csv(path: Path, rows: list[SweepRow]) -> None:
    if not rows:
        path.write_text("rank\n", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(asdict(rows[0]).keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))


def write_json(path: Path, rows: list[SweepRow], settings: dict[str, Any]) -> None:
    payload = {
        "settings": settings,
        "results": [asdict(row) for row in rows],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_ints(values: list[str]) -> list[int]:
    return [int(value) for value in values]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run multiple offline backtests over parameter combinations.")
    parser.add_argument("path", type=Path, help="Path to candles .json or .csv")
    parser.add_argument("--asset", default="SWEEP/ASSET")
    parser.add_argument("--durations", nargs="+", default=["180"], help="Trade durations in seconds")
    parser.add_argument("--candle-seconds", type=int, default=60, help="Seconds represented by each candle")
    parser.add_argument("--min-confidences", nargs="+", default=["70", "75", "80"])
    parser.add_argument("--lookbacks", nargs="+", default=["60", "90", "120"])
    parser.add_argument("--steps", nargs="+", default=["1"])
    parser.add_argument("--top", type=int, default=10, help="How many rows to print")
    parser.add_argument(
        "--keep-open-candle",
        action="store_true",
        help="Keep the latest candle in strategy windows. Default drops it to match live strategy behavior.",
    )
    parser.add_argument("--csv-out", type=Path, help="Optional CSV output path")
    parser.add_argument("--json-out", type=Path, help="Optional JSON output path")
    args = parser.parse_args()

    candles = load_candles(args.path)
    durations = parse_ints(args.durations)
    min_confidences = parse_ints(args.min_confidences)
    lookbacks = parse_ints(args.lookbacks)
    steps = parse_ints(args.steps)
    drop_open_candle = not args.keep_open_candle

    rows = run_sweep(
        candles=candles,
        asset=args.asset,
        durations=durations,
        min_confidences=min_confidences,
        lookbacks=lookbacks,
        steps=steps,
        candle_seconds=args.candle_seconds,
        drop_open_candle=drop_open_candle,
    )
    print_table(rows, limit=args.top)

    settings = {
        "source": str(args.path),
        "asset": args.asset,
        "durations": durations,
        "candle_seconds": args.candle_seconds,
        "drop_open_candle": drop_open_candle,
        "min_confidences": min_confidences,
        "lookbacks": lookbacks,
        "steps": steps,
        "candles": len(candles),
    }
    if args.csv_out:
        write_csv(args.csv_out, rows)
        print(f"CSV sweep written: {args.csv_out}")
    if args.json_out:
        write_json(args.json_out, rows, settings)
        print(f"JSON sweep written: {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
