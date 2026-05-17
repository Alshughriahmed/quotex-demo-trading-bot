from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path
from typing import Any


BOT_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BOT_DIR / "data.db"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Explore external trade filters without modifying native data.")
    parser.add_argument("--min-trades", type=int, default=10, help="Minimum trades per candidate group.")
    parser.add_argument("--limit", type=int, default=12, help="Rows to show per section.")
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


def confidence_expr() -> str:
    return """
    CASE
        WHEN confidence IS NULL THEN 'unknown'
        WHEN confidence < 70 THEN '<70'
        WHEN confidence < 80 THEN '70-79'
        WHEN confidence < 90 THEN '80-89'
        WHEN confidence < 95 THEN '90-94'
        ELSE '95-100'
    END
    """


def hour_expr() -> str:
    return "COALESCE(substr(entry_time, 12, 2), 'unknown')"


def money(value: Any) -> str:
    try:
        return f"{float(value or 0):.2f}"
    except (TypeError, ValueError):
        return "0.00"


def print_section(title: str) -> None:
    print("-" * 72)
    print(title)
    print("-" * 72)


def candidate_query(group_exprs: list[tuple[str, str]], min_trades: int, limit: int, best: bool) -> tuple[str, list[Any]]:
    select_parts = [f"{expr} AS {name}" for name, expr in group_exprs]
    group_parts = [expr for _, expr in group_exprs]
    order = "profit_loss DESC, trades DESC" if best else "profit_loss ASC, trades DESC"
    having = "profit_loss > 0" if best else "profit_loss < 0"
    query = f"""
        SELECT {', '.join(select_parts)},
               COUNT(*) AS trades,
               SUM(CASE WHEN result='WIN' THEN 1 ELSE 0 END) AS wins,
               SUM(CASE WHEN result='LOSS' THEN 1 ELSE 0 END) AS losses,
               SUM(CASE WHEN result='DRAW' THEN 1 ELSE 0 END) AS draws,
               ROUND(100.0 * SUM(CASE WHEN result='WIN' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) AS win_rate,
               SUM(COALESCE(profit_loss, 0)) AS profit_loss,
               AVG(COALESCE(profit_loss, 0)) AS avg_profit,
               CASE
                   WHEN ABS(SUM(CASE WHEN result='LOSS' THEN COALESCE(profit_loss, 0) ELSE 0 END)) > 0
                   THEN ROUND(SUM(CASE WHEN result='WIN' THEN COALESCE(profit_loss, 0) ELSE 0 END) /
                              ABS(SUM(CASE WHEN result='LOSS' THEN COALESCE(profit_loss, 0) ELSE 0 END)), 2)
                   ELSE NULL
               END AS profit_factor
        FROM external_trades
        GROUP BY {', '.join(group_parts)}
        HAVING trades >= ? AND {having}
        ORDER BY {order}
        LIMIT ?
    """
    return query, [min_trades, limit]


def fetch_candidates(
    db: sqlite3.Connection,
    group_exprs: list[tuple[str, str]],
    min_trades: int,
    limit: int,
    best: bool,
) -> list[sqlite3.Row]:
    query, params = candidate_query(group_exprs, min_trades, limit, best)
    return db.execute(query, params).fetchall()


def print_rows(title: str, rows: list[sqlite3.Row], group_names: list[str]) -> None:
    print_section(title)
    if not rows:
        print("No groups matched the threshold.")
        return
    columns = group_names + ["trades", "wins", "losses", "draws", "win_rate", "profit_loss", "avg_profit", "profit_factor"]
    print(" | ".join(columns))
    print(" | ".join("-" * len(column) for column in columns))
    for row in rows:
        values: list[str] = []
        for column in columns:
            value = row[column]
            if column in {"profit_loss", "avg_profit"}:
                values.append(money(value))
            elif column == "win_rate":
                values.append(f"{float(value or 0):.1f}%")
            elif column == "profit_factor":
                values.append("" if value is None else f"{float(value):.2f}")
            else:
                values.append(str(value if value is not None else ""))
        print(" | ".join(values))


def print_summary(db: sqlite3.Connection) -> None:
    row = db.execute(
        """
        SELECT COUNT(*) AS total,
               SUM(CASE WHEN result='WIN' THEN 1 ELSE 0 END) AS wins,
               SUM(CASE WHEN result='LOSS' THEN 1 ELSE 0 END) AS losses,
               SUM(CASE WHEN result='DRAW' THEN 1 ELSE 0 END) AS draws,
               SUM(COALESCE(profit_loss, 0)) AS profit_loss
        FROM external_trades
        """
    ).fetchone()
    total = int(row["total"] or 0)
    wins = int(row["wins"] or 0)
    losses = int(row["losses"] or 0)
    draws = int(row["draws"] or 0)
    profit_loss = float(row["profit_loss"] or 0)
    win_rate = (wins / total * 100) if total else 0
    print_section("Dataset baseline")
    print(f"Total external trades: {total}")
    print(f"Wins/Losses/Draws: {wins}/{losses}/{draws}")
    print(f"Win rate: {win_rate:.1f}%")
    print(f"Profit/Loss: {profit_loss:.2f}")
    print("These filter candidates are research hypotheses only, not execution rules.")


def main() -> int:
    args = parse_args()
    min_trades = max(1, args.min_trades)
    limit = max(1, args.limit)

    print("=" * 72)
    print("QTB external filter explorer")
    print("=" * 72)
    print(f"Database: {DB_PATH}")
    print("This reads external_* research tables only. It does not trade or modify native trades.")
    print(f"Minimum trades per group: {min_trades}")

    if not DB_PATH.exists():
        print("Database not found.")
        return 1

    groups = [
        ("Asset candidates", [("asset", "asset")]),
        ("Direction candidates", [("direction", "direction")]),
        ("Confidence candidates", [("confidence_bucket", confidence_expr())]),
        ("UTC hour candidates", [("hour_utc", hour_expr())]),
        ("Asset + direction candidates", [("asset", "asset"), ("direction", "direction")]),
        ("Asset + confidence candidates", [("asset", "asset"), ("confidence_bucket", confidence_expr())]),
        ("Direction + hour candidates", [("direction", "direction"), ("hour_utc", hour_expr())]),
        ("Asset + hour candidates", [("asset", "asset"), ("hour_utc", hour_expr())]),
        ("Asset + direction + confidence candidates", [
            ("asset", "asset"),
            ("direction", "direction"),
            ("confidence_bucket", confidence_expr()),
        ]),
    ]

    with connect() as db:
        if not table_exists(db, "external_trades"):
            print("external_trades table not found. Import external data first.")
            return 1

        print_summary(db)

        for title, group_exprs in groups:
            best_rows = fetch_candidates(db, group_exprs, min_trades, limit, best=True)
            print_rows(f"Best positive {title}", best_rows, [name for name, _ in group_exprs])

        for title, group_exprs in groups:
            worst_rows = fetch_candidates(db, group_exprs, min_trades, min(limit, 8), best=False)
            print_rows(f"Worst negative {title}", worst_rows, [name for name, _ in group_exprs])

    print("=" * 72)
    print("Filter exploration finished.")
    print("Important: require more data and out-of-sample validation before adopting any filter.")
    print("No secrets were printed and no native trades were changed.")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
