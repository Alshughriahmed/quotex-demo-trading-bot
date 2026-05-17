from __future__ import annotations

import argparse
import random
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import sys

BOT_DIR = Path(__file__).resolve().parents[1]
if str(BOT_DIR) not in sys.path:
    sys.path.insert(0, str(BOT_DIR))

import database


DEFAULT_DB_PATH = BOT_DIR / "data.db"
DEFAULT_ASSETS = ["GBP/USD", "EUR/USD", "USD/JPY"]
DEFAULT_STRATEGY = "paper_simulated_v1"

BASE_PRICES = {
    "GBP/USD": 1.2700,
    "EUR/USD": 1.0850,
    "USD/JPY": 155.00,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate local simulated DEMO trades for pipeline testing."
    )
    parser.add_argument(
        "--db",
        default=str(DEFAULT_DB_PATH),
        help="Path to local SQLite database. Defaults to bot/data.db.",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=25,
        help="Number of paper trades to generate.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Optional deterministic random seed.",
    )
    return parser.parse_args()


def ensure_database(db_path: Path) -> None:
    database.init_db(str(db_path), admin_ids=[], signals_chat_id=None)


def current_trade_count(db_path: Path) -> int:
    with sqlite3.connect(db_path) as db:
        row = db.execute("SELECT COUNT(*) FROM trades").fetchone()
        return int(row[0] or 0)


def make_trade(index: int, rng: random.Random) -> dict:
    asset = rng.choice(DEFAULT_ASSETS)
    direction = rng.choice(["CALL", "PUT"])
    confidence = rng.randint(70, 94)
    amount = rng.choice([1, 2, 3, 5, 10])
    duration_seconds = rng.choice([60, 120, 180, 300])
    payout = rng.choice([70, 72, 75, 80, 85, 88])
    entry_time = datetime.now(timezone.utc) - timedelta(minutes=(index + 1) * rng.randint(4, 11))
    signal_time = entry_time - timedelta(seconds=60)
    expiry_time = entry_time + timedelta(seconds=duration_seconds)

    base_price = BASE_PRICES.get(asset, 1.0)
    price_step = 0.0001 if "JPY" not in asset else 0.01
    entry_price = base_price + rng.uniform(-25, 25) * price_step
    move = rng.uniform(1, 8) * price_step

    # Slightly better than random, only for pipeline testing.
    win_probability = 0.48 + max(0, confidence - 75) * 0.01
    outcome_roll = rng.random()
    if outcome_roll < min(0.72, win_probability):
        result = "WIN"
    elif outcome_roll < min(0.78, win_probability + 0.05):
        result = "DRAW"
    else:
        result = "LOSS"

    if result == "DRAW":
        exit_price = entry_price
        profit_loss = 0
    else:
        if direction == "CALL":
            exit_price = entry_price + move if result == "WIN" else entry_price - move
        else:
            exit_price = entry_price - move if result == "WIN" else entry_price + move
        profit_loss = round(amount * (payout / 100), 2) if result == "WIN" else -amount

    rsi = rng.uniform(38, 68) if direction == "CALL" else rng.uniform(32, 58)
    ema_fast = entry_price + (rng.uniform(1, 8) * price_step * (1 if direction == "CALL" else -1))
    ema_slow = entry_price - (rng.uniform(1, 8) * price_step * (1 if direction == "CALL" else -1))
    ema_gap = abs(ema_fast - ema_slow)
    atr = rng.uniform(3, 16) * price_step
    adx = rng.uniform(16, 38)
    volatility = rng.uniform(0.0001, 0.0025)
    candle_body_ratio = rng.uniform(0.25, 0.85)

    return {
        "asset": asset,
        "direction": direction,
        "signal_time": signal_time.isoformat(timespec="seconds"),
        "entry_time": entry_time.isoformat(timespec="seconds"),
        "expiry_time": expiry_time.isoformat(timespec="seconds"),
        "duration_seconds": duration_seconds,
        "confidence": confidence,
        "amount": amount,
        "account_type": "DEMO",
        "entry_price": round(entry_price, 5),
        "exit_price": round(exit_price, 5),
        "result": result,
        "profit_loss": profit_loss,
        "rsi": round(rsi, 2),
        "ema_fast": round(ema_fast, 5),
        "ema_slow": round(ema_slow, 5),
        "ema_gap": round(ema_gap, 8),
        "adx": round(adx, 2),
        "atr": round(atr, 8),
        "payout": payout,
        "market_session": market_session(entry_time),
        "entry_delay_ms": rng.randint(0, 350),
        "buy_latency_ms": rng.randint(80, 900),
        "loss_streak": rng.randint(0, 3),
        "candle_body_ratio": round(candle_body_ratio, 4),
        "price_slippage": round(rng.uniform(-2, 2) * price_step, 8),
        "websocket_latency": None,
        "broker_open_delay_ms": rng.randint(-100, 700),
        "execution_offset_ms": rng.choice([0, 100, 150, 200, 250]),
        "trend": direction,
        "volatility": round(volatility, 8),
        "strategy_name": DEFAULT_STRATEGY,
        "decision_reason": "SIMULATED PAPER DATA - not a real market result",
        "telegram_signal_message_id": None,
        "telegram_result_message_id": None,
        "status": "CLOSED",
        "error_message": None,
    }


def market_session(entry_time: datetime) -> str:
    hour = entry_time.astimezone(timezone.utc).hour
    if 0 <= hour < 7:
        return "Asia"
    if 7 <= hour < 13:
        return "London"
    if 13 <= hour < 22:
        return "New York"
    return "Asia"


def main() -> int:
    args = parse_args()
    if args.count <= 0:
        raise SystemExit("--count must be greater than 0")

    db_path = Path(args.db).expanduser().resolve()
    rng = random.Random(args.seed)
    ensure_database(db_path)

    before = current_trade_count(db_path)
    for index in range(args.count):
        database.create_trade(str(db_path), make_trade(index, rng))
    after = current_trade_count(db_path)

    print(f"Generated {args.count} simulated paper trades.")
    print(f"Database: {db_path}")
    print(f"Trades before: {before}")
    print(f"Trades after:  {after}")
    print("These records are simulated and must not be treated as strategy performance.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
