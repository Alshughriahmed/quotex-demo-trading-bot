from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from dataclasses import asdict, dataclass
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

    @property
    def closed_trades(self) -> int:
        return self.wins + self.losses

    def to_summary_dict(self) -> dict[str, int | float]:
        return {
            "total_signals": self.total_signals,
            "wins": self.wins,
            "losses": self.losses,
            "draws": self.draws,
            "no_trade_windows": self.no_trade_windows,
            "closed_trades": self.closed_trades,
            "win_rate_excluding_draws": round(self.win_rate, 4),
            "win_rate_including_draws": round(self.accuracy_with_draws, 4),
        }


@dataclass(slots=True)
class BacktestTrade:
    index: int
    asset: str
    direction: str
    confidence: int
    reason: str
    entry_price: float
    exit_price: float
    outcome: str


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


def calculate_horizon(duration_seconds: int, candle_seconds: int) -> int:
    if duration_seconds <= 0:
        raise ValueError("duration_seconds must be greater than zero")
    if candle_seconds <= 0:
        raise ValueError("candle_seconds must be greater than zero")
    return max(1, int(math.ceil(duration_seconds / candle_seconds)))


def run_backtest(
    candles: list[dict[str, Any]],
    asset: str,
    duration_seconds: int,
    min_confidence: int,
    lookback: int,
    step: int,
    candle_seconds: int = 60,
    drop_open_candle: bool = True,
) -> tuple[BacktestResult, list[BacktestTrade]]:
    if step <= 0:
        raise ValueError("step must be greater than zero")
    if lookback <= 0:
        raise ValueError("lookback must be greater than zero")

    horizon = calculate_horizon(duration_seconds, candle_seconds)
    result = BacktestResult()
    trades: list[BacktestTrade] = []
    index = lookback
    last_entry_index = -10_000

    while index + horizon < len(candles):
        window = candles[index - lookback:index]
        decision = analyze(
            asset=asset,
            candles=window,
            duration_seconds=duration_seconds,
            min_confidence=min_confidence,
            drop_open_candle=drop_open_candle,
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
        trades.append(
            BacktestTrade(
                index=index,
                asset=asset,
                direction=decision.direction,
                confidence=decision.confidence,
                reason=decision.reason,
                entry_price=entry_price,
                exit_price=exit_price,
                outcome=outcome,
            )
        )
        last_entry_index = index
        index += step

    return result, trades


def decide_outcome(direction: str, entry_price: float, exit_price: float) -> str:
    if abs(entry_price - exit_price) <= 1e-12:
        return "DRAW"
    if direction == CALL:
        return "WIN" if exit_price > entry_price else "LOSS"
    if direction == PUT:
        return "WIN" if exit_price < entry_price else "LOSS"
    return "DRAW"


def print_report(result: BacktestResult) -> None:
    print("Offline strategy backtest")
    print("=========================")
    print(f"Signals: {result.total_signals}")
    print(f"Wins: {result.wins}")
    print(f"Losses: {result.losses}")
    print(f"Draws: {result.draws}")
    print(f"No-trade windows: {result.no_trade_windows}")
    print(f"Closed trades: {result.closed_trades}")
    print(f"Win rate excluding draws: {result.win_rate:.2f}%")
    print(f"Win rate including draws: {result.accuracy_with_draws:.2f}%")


def write_json_report(path: Path, result: BacktestResult, trades: list[BacktestTrade], settings: dict[str, Any]) -> None:
    payload = {
        "settings": settings,
        "summary": result.to_summary_dict(),
        "trades": [asdict(trade) for trade in trades],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_csv_report(path: Path, trades: list[BacktestTrade]) -> None:
    fieldnames = [
        "index",
        "asset",
        "direction",
        "confidence",
        "reason",
        "entry_price",
        "exit_price",
        "outcome",
    ]
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for trade in trades:
            writer.writerow(asdict(trade))


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline backtest for the local strategy logic.")
    parser.add_argument("path", type=Path, help="Path to candles .json or .csv")
    parser.add_argument("--asset", default="BACKTEST/ASSET")
    parser.add_argument("--duration", type=int, default=180, help="Trade duration in seconds")
    parser.add_argument("--candle-seconds", type=int, default=60, help="Seconds represented by each candle")
    parser.add_argument("--min-confidence", type=int, default=75)
    parser.add_argument("--lookback", type=int, default=90, help="Number of candles per strategy window")
    parser.add_argument("--step", type=int, default=1, help="How many candles to move after each scan")
    parser.add_argument(
        "--keep-open-candle",
        action="store_true",
        help="Keep the latest candle in strategy windows. Default drops it to match live strategy behavior.",
    )
    parser.add_argument("--json-out", type=Path, help="Optional path to write a JSON backtest report")
    parser.add_argument("--csv-out", type=Path, help="Optional path to write a CSV trade list")
    args = parser.parse_args()

    candles = load_candles(args.path)
    horizon = calculate_horizon(args.duration, args.candle_seconds)
    if len(candles) < args.lookback + horizon + 1:
        raise SystemExit("Not enough candles for this lookback, duration, and candle size.")

    drop_open_candle = not args.keep_open_candle
    result, trades = run_backtest(
        candles=candles,
        asset=args.asset,
        duration_seconds=args.duration,
        min_confidence=args.min_confidence,
        lookback=args.lookback,
        step=args.step,
        candle_seconds=args.candle_seconds,
        drop_open_candle=drop_open_candle,
    )
    print_report(result)

    settings = {
        "source": str(args.path),
        "asset": args.asset,
        "duration_seconds": args.duration,
        "candle_seconds": args.candle_seconds,
        "horizon_candles": horizon,
        "drop_open_candle": drop_open_candle,
        "min_confidence": args.min_confidence,
        "lookback": args.lookback,
        "step": args.step,
        "candles": len(candles),
    }
    if args.json_out:
        write_json_report(args.json_out, result, trades, settings)
        print(f"JSON report written: {args.json_out}")
    if args.csv_out:
        write_csv_report(args.csv_out, trades)
        print(f"CSV trades written: {args.csv_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
