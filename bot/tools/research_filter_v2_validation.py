from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

BOT_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BOT_DIR / "data.db"

BAD_ASSETS = {
    "NZD/CAD", "GBP/NZD", "CAD/CHF", "AUD/USD", "USD/BDT",
    "EUR/USD", "NZD/JPY", "USD/CHF", "CAD/JPY",
}
BAD_HOURS = {"07", "08", "09", "12", "14", "17", "22", "23"}
GOOD_ASSETS = {"USD/NGN", "USD/CAD", "AUD/JPY", "USD/PKR", "USD/JPY", "AUD/CAD"}
ALLOW_CALL_ASSETS = {"USD/CAD", "USD/JPY"}
ALLOW_COMBOS = {("USD/CAD", "CALL"), ("USD/JPY", "CALL"), ("USD/PKR", "PUT"), ("NZD/USD", "PUT")}


@dataclass(frozen=True)
class Row:
    asset: str
    direction: str
    hour: str
    result: str
    profit: float
    entry_time: str


@dataclass(frozen=True)
class Rule:
    name: str
    note: str
    keep: Callable[[Row], bool]


def load_rows() -> list[Row]:
    with sqlite3.connect(DB_PATH) as db:
        db.row_factory = sqlite3.Row
        rows = db.execute(
            """
            SELECT asset, direction, result, COALESCE(profit_loss, 0) AS profit_loss,
                   entry_time, strftime('%H', entry_time) AS hour_utc
            FROM external_trades
            WHERE entry_time IS NOT NULL
            ORDER BY entry_time, id
            """
        ).fetchall()
    return [
        Row(
            asset=str(r["asset"] or ""),
            direction=str(r["direction"] or ""),
            hour=str(r["hour_utc"] or ""),
            result=str(r["result"] or ""),
            profit=float(r["profit_loss"] or 0),
            entry_time=str(r["entry_time"] or ""),
        )
        for r in rows
    ]


def metrics(rows: list[Row], rule: Rule) -> dict[str, float | int | str]:
    kept = [row for row in rows if rule.keep(row)]
    trades = len(kept)
    wins = sum(1 for row in kept if row.result == "WIN")
    losses = sum(1 for row in kept if row.result == "LOSS")
    draws = sum(1 for row in kept if row.result == "DRAW")
    profit = round(sum(row.profit for row in kept), 2)
    win_rate = round((wins / trades * 100), 1) if trades else 0.0
    avg = round((profit / trades), 2) if trades else 0.0
    return {
        "trades": trades,
        "wins": wins,
        "losses": losses,
        "draws": draws,
        "win_rate": win_rate,
        "profit_loss": profit,
        "avg_profit": avg,
    }


def rules() -> list[Rule]:
    return [
        Rule("baseline", "all external research rows", lambda r: True),
        Rule("no_bad_assets", "exclude historically weak assets", lambda r: r.asset not in BAD_ASSETS),
        Rule("no_bad_hours", "exclude historically weak UTC hours", lambda r: r.hour not in BAD_HOURS),
        Rule("no_bad_assets_hours", "exclude weak assets and weak hours", lambda r: r.asset not in BAD_ASSETS and r.hour not in BAD_HOURS),
        Rule("combos_only", "only first positive asset/direction pairs", lambda r: (r.asset, r.direction) in ALLOW_COMBOS),
        Rule("combos_no_bad_hours", "positive pairs outside weak hours", lambda r: (r.asset, r.direction) in ALLOW_COMBOS and r.hour not in BAD_HOURS),
        Rule("conservative_v1", "no weak assets/hours; CALL only on USD/CAD or USD/JPY", lambda r: r.asset not in BAD_ASSETS and r.hour not in BAD_HOURS and (r.direction != "CALL" or r.asset in ALLOW_CALL_ASSETS)),
        Rule("positive_assets_no_bad_hours", "only first positive assets outside weak hours", lambda r: r.asset in GOOD_ASSETS and r.hour not in BAD_HOURS),
        Rule("put_no_bad_assets_hours", "PUT only after weak asset/hour removal", lambda r: r.direction == "PUT" and r.asset not in BAD_ASSETS and r.hour not in BAD_HOURS),
    ]


def fmt(value: object) -> str:
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def print_table(title: str, rows: list[dict[str, object]], cols: list[str]) -> None:
    print("-" * 72)
    print(title)
    print("-" * 72)
    print(" | ".join(cols))
    print(" | ".join("-" * len(c) for c in cols))
    for row in rows:
        print(" | ".join(fmt(row.get(c, "")) for c in cols))


def status(train: dict[str, object], valid: dict[str, object]) -> str:
    train_trades = int(train["trades"])
    valid_trades = int(valid["trades"])
    train_pl = float(train["profit_loss"])
    valid_pl = float(valid["profit_loss"])
    valid_wr = float(valid["win_rate"])
    if valid_trades < 30:
        return "TOO_SMALL"
    if train_pl > 0 and valid_pl > 0 and valid_wr >= 52:
        return "RESEARCH_KEEP"
    if valid_pl > 0:
        return "WATCH_ONLY"
    return "REJECT_NOW"


def main() -> int:
    print("=" * 72)
    print("QTB research filter v2 validation")
    print("=" * 72)
    print("This report validates filter ideas on older vs newer external research rows only.")
    print("It does not start the bot, does not connect anywhere, and does not modify native trades.")
    print(f"Database: {DB_PATH}")

    if not DB_PATH.exists():
        print("Database not found.")
        return 1

    data = load_rows()
    if not data:
        print("No external rows found.")
        return 0

    split_at = max(1, int(len(data) * 0.70))
    train = data[:split_at]
    valid = data[split_at:]
    print(f"Total rows: {len(data)}")
    print(f"Train rows older 70%: {len(train)} | {train[0].entry_time} -> {train[-1].entry_time}")
    print(f"Validation rows newer 30%: {len(valid)} | {valid[0].entry_time} -> {valid[-1].entry_time}")

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
                "status": status(train_m, valid_m),
            }
        )

    print_table(
        "Chronological validation comparison",
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
    print("Keep only rules that survive the newer validation part. Anything else is overfitting risk.")
    print("The next stronger test is replay on real candle CSV data, then live signal-only collection.")
    print("=" * 72)
    print("Research filter v2 validation finished. No native trades were changed.")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
