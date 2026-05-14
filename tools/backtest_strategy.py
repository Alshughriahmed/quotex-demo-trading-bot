from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bot"))

from trading.strategy import CALL, NO_TRADE, PUT, analyze  # noqa: E402


@dataclass(slots=True)
class BacktestResult:
    total_signals: int = 0
    wins: int = 0
    losses: int = 0
    draws: int = 0
    no_trade_windows: int = 0

    @property
    def win_rate(self) -> float:
        closed = self.wins + self.losses
        if closed == 0:
            return 0.0
        return (self.wins / closed) * 100

    @property
    def accuracy_with_draws(self) -> float:
        total = self.wins + self.losses + self.draws
        if total == 0:
            return 0.0
        return (self.wins / total) * 100


def load_candles(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".json":
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
        if isinstance(data, dict):
            data = data.get("candles") or data.get("data") or []
        if not isinstance(data, list):
            raise ValueError("JSON file must contain a list of candles or a {'candles': [...]} object.")
        return [normalize_input_candle(item) for item in data]

    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8", newline="") as file:
            reader = csv.DictReader(file)
            return [normalize_input_candle(row) for row in reader]

    raise ValueError("Unsupported file type. Use .json or .csv")


def normalize_input_candle(row: dict[str, Any]) -> dict[str, float]:
    return {
        "time": float(row.get("time") or row.get("timestamp") or row.get("from") or 0),
        "open": float(row["open"]),
        "high": float(row["high"]),
        "low": float(row["low"]),
        "close": float(row["close"]),
    }


def run_backtest(
    candles: list[dict[str, Any]],
    asset: str,
    duration_seconds: int,
    min_confidence: int,
    lookback: int,
    step: int,
) -> BacktestResult:
    if step <= 0:
        raise ValueError("step must be greater than zero")
    if lookback <= 0:
        raise ValueError("lookback must be greater than zero")

    horizon = max(1, duration_seconds // 60)
    result = BacktestResult()
    index = lookback
    last_entry_index = -10_000

    while index + horizon < len(candles):
        window = candles[index - lookback:index]
        decision = analyze(
            asset=asset,
            candles=window,
            duration_seconds=duration_seconds,
            min_confidence=min_confidence,
            drop_open_candle=False,
        )

        if decision.direction == NO_TRADE:
            result.no_trade_windows += 1
            index += step
            continue

        if index <= last_entry_index + horizon:
            index += step
            continue

        entry_price = float(candles[index]["open"])
        exit_price = float(candles[index + horizon]["close"])
        outcome = decide_outcome(decision.direction, entry_price, exit_price)
        result.total_signals += 1
        if outcome == "WIN":
            result.wins += 1
        elif outcome == "LOSS":
            result.losses += 1
        else:
            result.draws += 1
        last_entry_index = index
        index += step

    return result


def decide_outcome(direction: str, entry_price: float, exit_price: float) -> str:
    if abs(entry_price - exit_price) <= 1e-12:
        return "DRAW"
    if direction == CALL:
        return "WIN" if exit_price > entry_price else "LOSS"
    if direction == PUT:
        return "WIN" if exit_price < entry_price else "LOSS"
    return "DRAW"


def print_report(result: BacktestResult) -> None:
    closed = result.wins + result.losses
    print("Offline strategy backtest")
    print("=========================")
    print(f"Signals: {result.total_signals}")
    print(f"Wins: {result.wins}")
    print(f"Losses: {result.losses}")
    print(f"Draws: {result.draws}")
    print(f"No-trade windows: {result.no_trade_windows}")
    print(f"Closed trades: {closed}")
    print(f"Win rate excluding draws: {result.win_rate:.2f}%")
    print(f"Win rate including draws: {result.accuracy_with_draws:.2f}%")


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline backtest for the local strategy logic.")
    parser.add_argument("path", type=Path, help="Path to candles .json or .csv")
    parser.add_argument("--asset", default="BACKTEST/ASSET")
    parser.add_argument("--duration", type=int, default=180, help="Trade duration in seconds")
    parser.add_argument("--min-confidence", type=int, default=75)
    parser.add_argument("--lookback", type=int, default=90, help="Number of candles per strategy window")
    parser.add_argument("--step", type=int, default=1, help="How many candles to move after each scan")
    args = parser.parse_args()

    candles = load_candles(args.path)
    if len(candles) < args.lookback + max(1, args.duration // 60) + 1:
        raise SystemExit("Not enough candles for this lookback and duration.")

    result = run_backtest(
        candles=candles,
        asset=args.asset,
        duration_seconds=args.duration,
        min_confidence=args.min_confidence,
        lookback=args.lookback,
        step=args.step,
    )
    print_report(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
