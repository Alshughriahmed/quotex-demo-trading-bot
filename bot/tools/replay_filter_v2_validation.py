from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

BOT_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BOT_DIR / "data.db"


@dataclass(frozen=True)
class ReplayRow:
    asset: str
    direction: str
    hour: str
    result: str
    profit: float
    signal_time: str


@dataclass(frozen=True)
class Rule:
    name: str
    note: str
    keep: Callable[[ReplayRow], bool]


def connect() -> sqlite3.Connection:
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    return db


def load_rows() -> list[ReplayRow]:
    with connect() as db:
        rows = db.execute(
            """
            SELECT s.asset,
                   s.direction,
                   COALESCE(s.entry_time, s.signal_time) AS signal_time,
                   strftime('%H', COALESCE(s.entry_time, s.signal_time)) AS hour_utc,
                   o.result,
                   COALESCE(o.theoretical_profit_loss, 0) AS profit_loss
            FROM research_signals s
            JOIN research_signal_outcomes o ON o.signal_id = s.id
            WHERE s.direction IN ('CALL','PUT')
            ORDER BY COALESCE(s.entry_time, s.signal_time), s.id
            """
        ).fetchall()
    return [
        ReplayRow(
            asset=str(row["asset"] or ""),
            direction=str(row["direction"] or ""),
            hour=str(row["hour_utc"] or ""),
            result=str(row["result"] or ""),
            profit=float(row["profit_loss"] or 0),
            signal_time=str(row["signal_time"] or ""),
        )
        for row in rows
    ]


def metrics(rows: list[ReplayRow], rule: Rule) -> dict[str, object]:
    kept = [row for row in rows if rule.keep(row)]
    trades = len(kept)
    wins = sum(1 for row in kept if row.result == "WIN")
    losses = sum(1 for row in kept if row.result == "LOSS")
    draws = sum(1 for row in kept if row.result == "DRAW")
    profit = round(sum(row.profit for row in kept), 2)
    return {
        "trades": trades,
        "wins": wins,
        "losses": losses,
        "draws": draws,
        "win_rate": round(wins / trades * 100, 1) if trades else 0.0,
        "profit_loss": profit,
        "avg_profit": round(profit / trades, 3) if trades else 0.0,
    }


def rules() -> list[Rule]:
    return [
        Rule("baseline", "all evaluated replay signals", lambda r: True),
        Rule("only_put", "PUT only", lambda r: r.direction == "PUT"),
        Rule("only_call", "CALL only", lambda r: r.direction == "CALL"),
        Rule("only_hours_15_08_09", "only first positive replay hours", lambda r: r.hour in {"15", "08", "09"}),
        Rule("put_hours_08_09_15", "PUT only during first positive replay hours", lambda r: r.direction == "PUT" and r.hour in {"08", "09", "15"}),
        Rule("put_hours_08_15", "PUT only during the two strongest replay hours", lambda r: r.direction == "PUT" and r.hour in {"08", "15"}),
        Rule("exclude_worst_hours_12_17", "exclude two worst replay hours", lambda r: r.hour not in {"12", "17"}),
        Rule("exclude_worst_hours_12_17_11_06", "exclude four worst replay hours", lambda r: r.hour not in {"12", "17", "11", "06"}),
        Rule("put_exclude_worst_hours_12_17", "PUT only while excluding two worst replay hours", lambda r: r.direction == "PUT" and r.hour not in {"12", "17"}),
        Rule("call_only_hours_01_18", "CALL only during first positive CALL hours", lambda r: r.direction == "CALL" and r.hour in {"01", "18"}),
    ]


def verdict(train: dict[str, object], valid: dict[str, object]) -> str:
    train_trades = int(train["trades"])
    valid_trades = int(valid["trades"])
    train_pl = float(train["profit_loss"])
    valid_pl = float(valid["profit_loss"])
    valid_wr = float(valid["win_rate"])
    if train_trades < 30 or valid_trades < 15:
        return "TOO_SMALL"
    if train_pl > 0 and valid_pl > 0 and valid_wr >= 52:
        return "RESEARCH_KEEP"
    if valid_pl > 0:
        return "WATCH_ONLY"
    return "REJECT_NOW"


def fmt(value: object) -> str:
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def print_table(title: str, rows: list[dict[str, object]], cols: list[str]) -> None:
    print("-" * 72)
    print(title)
    print("-" * 72)
    print(" | ".join(cols))
    print(" | ".join("-" * len(col) for col in cols))
    for row in rows:
        print(" | ".join(fmt(row.get(col, "")) for col in cols))


def main() -> int:
    print("=" * 72)
    print("QTB replay filter v2 chronological validation")
    print("=" * 72)
    print("This validates replay filter hypotheses on older vs newer replay results only.")
    print("It does not start the bot, does not connect anywhere, and does not modify native trades.")
    print(f"Database: {DB_PATH}")

    if not DB_PATH.exists():
        print("Database not found.")
        return 1

    data = load_rows()
    if not data:
        print("No evaluated replay rows found yet.")
        return 0

    split_at = max(1, int(len(data) * 0.70))
    train = data[:split_at]
    valid = data[split_at:]
    print(f"Total replay rows: {len(data)}")
    print(f"Train older 70%: {len(train)} | {train[0].signal_time} -> {train[-1].signal_time}")
    print(f"Validation newer 30%: {len(valid)} | {valid[0].signal_time} -> {valid[-1].signal_time}")

    comparison: list[dict[str, object]] = []
    for rule in rules():
        all_m = metrics(data, rule)
        train_m = metrics(train, rule)
        valid_m = metrics(valid, rule)
        comparison.append(
            {
                "rule": rule.name,
                "all_trades": all_m["trades"],
                "all_wr": all_m["win_rate"],
                "all_pl": all_m["profit_loss"],
                "train_trades": train_m["trades"],
                "train_wr": train_m["win_rate"],
                "train_pl": train_m["profit_loss"],
                "valid_trades": valid_m["trades"],
                "valid_wr": valid_m["win_rate"],
                "valid_pl": valid_m["profit_loss"],
                "status": verdict(train_m, valid_m),
            }
        )

    print_table(
        "Replay chronological validation comparison",
        comparison,
        ["rule", "all_trades", "all_wr", "all_pl", "train_trades", "train_wr", "train_pl", "valid_trades", "valid_wr", "valid_pl", "status"],
    )

    print("-" * 72)
    print("Rule notes")
    print("-" * 72)
    for rule in rules():
        print(f"{rule.name}: {rule.note}")

    print("-" * 72)
    print("Decision")
    print("-" * 72)
    print("Keep only rules that survive the newer validation window. Others are likely overfit.")
    print("One month and one pair are not enough. Repeat with more months and pairs before changing strategy logic.")
    print("=" * 72)
    print("Replay filter v2 validation finished. No native trades were changed.")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
