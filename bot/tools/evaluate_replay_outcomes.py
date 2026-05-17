from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


BOT_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BOT_DIR / "data.db"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate replay research signal outcomes from stored candles.")
    parser.add_argument("--source-key", default="", help="Optional source_key filter.")
    parser.add_argument("--asset", default="", help="Optional asset filter.")
    parser.add_argument("--payout", type=float, default=0.80, help="Theoretical payout for wins, e.g. 0.80.")
    parser.add_argument("--include-no-trade", action="store_true", help="Evaluate NO_TRADE rows as UNKNOWN outcomes.")
    parser.add_argument("--yes", action="store_true", help="Actually insert outcomes. Without this flag, dry-run only.")
    return parser.parse_args()


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def table_exists(db: sqlite3.Connection, table_name: str) -> bool:
    row = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone()
    return row is not None


def parse_time(value: str) -> datetime:
    text = str(value or "").strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def load_pending_signals(db: sqlite3.Connection, source_key: str, asset: str, include_no_trade: bool) -> list[sqlite3.Row]:
    where = ["o.id IS NULL"]
    params: list[Any] = []
    if source_key:
        where.append("s.source_key = ?")
        params.append(source_key)
    if asset:
        where.append("s.asset = ?")
        params.append(asset)
    if not include_no_trade:
        where.append("s.direction IN ('CALL', 'PUT')")

    return db.execute(
        f"""
        SELECT s.*
        FROM research_signals s
        LEFT JOIN research_signal_outcomes o ON o.signal_id = s.id
        WHERE {' AND '.join(where)}
        ORDER BY s.source_key, s.asset, s.signal_time, s.id
        """,
        tuple(params),
    ).fetchall()


def find_price_at_or_after(
    db: sqlite3.Connection,
    source_key: str,
    asset: str,
    timeframe_seconds: int,
    target_time: str,
) -> sqlite3.Row | None:
    return db.execute(
        """
        SELECT *
        FROM research_market_candles
        WHERE source_key = ?
          AND asset = ?
          AND timeframe_seconds = ?
          AND candle_time >= ?
        ORDER BY candle_time ASC
        LIMIT 1
        """,
        (source_key, asset, timeframe_seconds, target_time),
    ).fetchone()


def evaluate_signal(db: sqlite3.Connection, signal: sqlite3.Row, payout: float) -> dict[str, Any] | None:
    direction = str(signal["direction"])
    if direction == "NO_TRADE":
        return {
            "signal_id": int(signal["id"]),
            "outcome_time": str(signal["signal_time"]),
            "entry_price": None,
            "exit_price": None,
            "result": "UNKNOWN",
            "theoretical_profit_loss": 0.0,
            "payout": payout,
            "notes": "NO_TRADE research row; no market outcome evaluated.",
        }

    signal_time = parse_time(str(signal["entry_time"] or signal["signal_time"]))
    expiry_text = str(signal["expiry_time"] or "").strip()
    if expiry_text:
        expiry_time = parse_time(expiry_text)
    else:
        expiry_time = signal_time.replace()  # defensive copy
        expiry_time = expiry_time.fromtimestamp(signal_time.timestamp() + int(signal["duration_seconds"]), tz=timezone.utc)

    timeframe = int(signal["duration_seconds"] or 60)
    entry_row = find_price_at_or_after(
        db,
        str(signal["source_key"]),
        str(signal["asset"]),
        timeframe,
        signal_time.isoformat(),
    )
    exit_row = find_price_at_or_after(
        db,
        str(signal["source_key"]),
        str(signal["asset"]),
        timeframe,
        expiry_time.isoformat(),
    )

    if not entry_row or not exit_row:
        return None

    entry_price = float(entry_row["close"])
    exit_price = float(exit_row["close"])
    if exit_price == entry_price:
        result = "DRAW"
        profit_loss = 0.0
    elif direction == "CALL" and exit_price > entry_price:
        result = "WIN"
        profit_loss = payout
    elif direction == "PUT" and exit_price < entry_price:
        result = "WIN"
        profit_loss = payout
    else:
        result = "LOSS"
        profit_loss = -1.0

    return {
        "signal_id": int(signal["id"]),
        "outcome_time": str(exit_row["candle_time"]),
        "entry_price": entry_price,
        "exit_price": exit_price,
        "result": result,
        "theoretical_profit_loss": profit_loss,
        "payout": payout,
        "notes": f"Replay evaluation using close price: entry={entry_row['candle_time']}, exit={exit_row['candle_time']}",
    }


def insert_outcome(db: sqlite3.Connection, outcome: dict[str, Any]) -> None:
    db.execute(
        """
        INSERT INTO research_signal_outcomes (
            signal_id,
            outcome_time,
            entry_price,
            exit_price,
            result,
            theoretical_profit_loss,
            payout,
            evaluation_method,
            notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 'replay_close_to_close', ?)
        """,
        (
            outcome["signal_id"],
            outcome["outcome_time"],
            outcome["entry_price"],
            outcome["exit_price"],
            outcome["result"],
            outcome["theoretical_profit_loss"],
            outcome["payout"],
            outcome["notes"],
        ),
    )


def summarize(outcomes: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {"WIN": 0, "LOSS": 0, "DRAW": 0, "UNKNOWN": 0, "profit_loss": 0.0}
    for outcome in outcomes:
        result = str(outcome["result"])
        summary[result] = int(summary.get(result, 0)) + 1
        summary["profit_loss"] = float(summary["profit_loss"]) + float(outcome["theoretical_profit_loss"] or 0)
    return summary


def main() -> int:
    args = parse_args()
    payout = max(0.0, min(1.0, float(args.payout)))

    print("=" * 72)
    print("QTB replay signal outcome evaluator")
    print("=" * 72)
    print("This evaluates research_signals against replay candles only.")
    print("It does not start the bot, does not connect to a broker, and does not trade.")
    print(f"Database: {DB_PATH}")
    print(f"Theoretical payout: {payout:.2f}")

    if not DB_PATH.exists():
        print("Database not found. Run init_signal_research_tables first.")
        return 1

    with connect() as db:
        if not table_exists(db, "research_signals") or not table_exists(db, "research_signal_outcomes"):
            print("Research signal tables are missing. Run init_signal_research_tables first.")
            return 1

        signals = load_pending_signals(db, args.source_key.strip(), args.asset.strip(), args.include_no_trade)
        print(f"Pending signals found: {len(signals)}")
        outcomes: list[dict[str, Any]] = []
        skipped = 0
        for signal in signals:
            outcome = evaluate_signal(db, signal, payout)
            if outcome is None:
                skipped += 1
                continue
            outcomes.append(outcome)

        summary = summarize(outcomes)
        print(f"Evaluable outcomes: {len(outcomes)}")
        print(f"Skipped without matching candles: {skipped}")
        print(f"WIN/LOSS/DRAW/UNKNOWN: {summary.get('WIN', 0)}/{summary.get('LOSS', 0)}/{summary.get('DRAW', 0)}/{summary.get('UNKNOWN', 0)}")
        print(f"Theoretical profit/loss: {float(summary.get('profit_loss', 0.0)):.2f}")

        if not args.yes:
            print("Dry run only. Re-run with --yes to insert research_signal_outcomes.")
            return 0

        for outcome in outcomes:
            insert_outcome(db, outcome)
        db.commit()
        print(f"Inserted outcomes: {len(outcomes)}")

    print("=" * 72)
    print("Replay outcome evaluation finished. No native trades were changed.")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
