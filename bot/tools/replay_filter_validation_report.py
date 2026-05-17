from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from typing import Any

BOT_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BOT_DIR / "data.db"
if str(BOT_DIR) not in sys.path:
    sys.path.insert(0, str(BOT_DIR))

from research_filters import evaluate_research_candidate, filter_summary


def connect() -> sqlite3.Connection:
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    return db


def table_exists(db: sqlite3.Connection, table: str) -> bool:
    row = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
    return row is not None


def get_rows(db: sqlite3.Connection) -> list[sqlite3.Row]:
    return db.execute(
        """
        SELECT s.id AS signal_id,
               s.asset,
               s.direction,
               s.signal_time,
               s.entry_time,
               s.expiry_time,
               s.confidence,
               o.result,
               COALESCE(o.theoretical_profit_loss, 0) AS theoretical_profit_loss,
               strftime('%H', COALESCE(s.entry_time, s.signal_time)) AS hour_utc
        FROM research_signals s
        JOIN research_signal_outcomes o ON o.signal_id = s.id
        WHERE s.direction IN ('CALL', 'PUT')
        ORDER BY COALESCE(s.entry_time, s.signal_time), s.id
        """
    ).fetchall()


def summarize(rows: list[sqlite3.Row]) -> dict[str, Any]:
    trades = len(rows)
    wins = sum(1 for row in rows if row["result"] == "WIN")
    losses = sum(1 for row in rows if row["result"] == "LOSS")
    draws = sum(1 for row in rows if row["result"] == "DRAW")
    profit = round(sum(float(row["theoretical_profit_loss"] or 0) for row in rows), 2)
    return {
        "trades": trades,
        "wins": wins,
        "losses": losses,
        "draws": draws,
        "win_rate": round((wins / trades * 100), 1) if trades else 0.0,
        "profit_loss": profit,
        "avg_profit": round((profit / trades), 2) if trades else 0.0,
    }


def print_summary(name: str, data: dict[str, Any]) -> None:
    print(f"{name} | {data['trades']} | {data['wins']} | {data['losses']} | {data['draws']} | {data['win_rate']} | {data['profit_loss']} | {data['avg_profit']}")


def print_blocked_reasons(blocked: dict[str, int]) -> None:
    print("-" * 72)
    print("Blocked reasons")
    print("-" * 72)
    if not blocked:
        print("No blocked replay signals.")
        return
    for reason, count in sorted(blocked.items(), key=lambda item: (-item[1], item[0])):
        print(f"{reason}: {count}")


def main() -> int:
    print("=" * 72)
    print("QTB replay filter validation report")
    print("=" * 72)
    print("This reads replay research signals/outcomes only. It does not trade and does not modify native trades.")
    print(f"Database: {DB_PATH}")

    if not DB_PATH.exists():
        print("Database not found.")
        return 1

    summary = filter_summary()
    print(f"Filter: {summary['name']}")
    print(f"Version: {summary['version']}")

    with connect() as db:
        missing = [name for name in ("research_signals", "research_signal_outcomes") if not table_exists(db, name)]
        if missing:
            print(f"Missing research tables: {', '.join(missing)}")
            return 1

        rows = get_rows(db)
        if not rows:
            print("No evaluated replay signals found yet.")
            print("Import real candle CSV, run replay signals, evaluate outcomes, then run this report again.")
            print("=" * 72)
            return 0

        allowed: list[sqlite3.Row] = []
        blocked: list[sqlite3.Row] = []
        blocked_reasons: dict[str, int] = {}
        for row in rows:
            decision = evaluate_research_candidate(row["asset"], row["direction"], row["hour_utc"])
            if decision.allowed:
                allowed.append(row)
            else:
                blocked.append(row)
                blocked_reasons[decision.reason] = blocked_reasons.get(decision.reason, 0) + 1

        print("-" * 72)
        print("Replay filter comparison")
        print("-" * 72)
        print("scope | trades | wins | losses | draws | win_rate | profit_loss | avg_profit")
        print("----- | ------ | ---- | ------ | ----- | -------- | ----------- | ----------")
        print_summary("baseline_all_replay", summarize(rows))
        print_summary("allowed_by_research_filter", summarize(allowed))
        print_summary("blocked_by_research_filter", summarize(blocked))

        print_blocked_reasons(blocked_reasons)

        print("-" * 72)
        print("Decision")
        print("-" * 72)
        print("If allowed_by_research_filter is better than baseline on real replay data, keep testing it.")
        print("If it fails on replay, discard or redesign it. Do not enable live execution from this report alone.")

    print("=" * 72)
    print("Replay filter validation finished. No native trades were changed.")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
