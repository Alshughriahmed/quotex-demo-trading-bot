from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


BOT_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BOT_DIR / "data.db"


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


def scalar(db: sqlite3.Connection, query: str, params: tuple[Any, ...] = ()) -> Any:
    row = db.execute(query, params).fetchone()
    if not row:
        return None
    return row[0]


def percent(part: float, total: float) -> str:
    if not total:
        return "0.0%"
    return f"{(part / total) * 100:.1f}%"


def money(value: Any) -> str:
    try:
        return f"{float(value or 0):.2f}"
    except (TypeError, ValueError):
        return "0.00"


def print_section(title: str) -> None:
    print("-" * 72)
    print(title)
    print("-" * 72)


def print_rows(title: str, rows: list[sqlite3.Row], columns: list[str]) -> None:
    print_section(title)
    if not rows:
        print("No data.")
        return
    print(" | ".join(columns))
    print(" | ".join("-" * len(c) for c in columns))
    for row in rows:
        values = []
        for column in columns:
            value = row[column]
            if column in {"profit_loss", "avg_profit"}:
                values.append(money(value))
            elif column in {"win_rate"}:
                values.append(f"{float(value or 0):.1f}%")
            else:
                values.append(str(value if value is not None else ""))
        print(" | ".join(values))


def load_summary(db: sqlite3.Connection) -> sqlite3.Row:
    return db.execute(
        """
        SELECT COUNT(*) AS total,
               SUM(CASE WHEN result='WIN' THEN 1 ELSE 0 END) AS wins,
               SUM(CASE WHEN result='LOSS' THEN 1 ELSE 0 END) AS losses,
               SUM(CASE WHEN result='DRAW' THEN 1 ELSE 0 END) AS draws,
               SUM(CASE WHEN result IS NULL OR result NOT IN ('WIN','LOSS','DRAW') THEN 1 ELSE 0 END) AS other,
               SUM(COALESCE(profit_loss, 0)) AS profit_loss,
               AVG(COALESCE(profit_loss, 0)) AS avg_profit,
               MIN(entry_time) AS first_entry,
               MAX(entry_time) AS last_entry
        FROM external_trades
        """
    ).fetchone()


def grouped_rows(db: sqlite3.Connection, group_expr: str, label: str, limit: int = 12) -> list[sqlite3.Row]:
    return db.execute(
        f"""
        SELECT {group_expr} AS {label},
               COUNT(*) AS trades,
               SUM(CASE WHEN result='WIN' THEN 1 ELSE 0 END) AS wins,
               SUM(CASE WHEN result='LOSS' THEN 1 ELSE 0 END) AS losses,
               SUM(CASE WHEN result='DRAW' THEN 1 ELSE 0 END) AS draws,
               ROUND(100.0 * SUM(CASE WHEN result='WIN' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) AS win_rate,
               SUM(COALESCE(profit_loss, 0)) AS profit_loss,
               AVG(COALESCE(profit_loss, 0)) AS avg_profit
        FROM external_trades
        GROUP BY {group_expr}
        ORDER BY profit_loss DESC, trades DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()


def grouped_rows_worst(db: sqlite3.Connection, group_expr: str, label: str, limit: int = 12) -> list[sqlite3.Row]:
    return db.execute(
        f"""
        SELECT {group_expr} AS {label},
               COUNT(*) AS trades,
               SUM(CASE WHEN result='WIN' THEN 1 ELSE 0 END) AS wins,
               SUM(CASE WHEN result='LOSS' THEN 1 ELSE 0 END) AS losses,
               SUM(CASE WHEN result='DRAW' THEN 1 ELSE 0 END) AS draws,
               ROUND(100.0 * SUM(CASE WHEN result='WIN' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) AS win_rate,
               SUM(COALESCE(profit_loss, 0)) AS profit_loss,
               AVG(COALESCE(profit_loss, 0)) AS avg_profit
        FROM external_trades
        GROUP BY {group_expr}
        ORDER BY profit_loss ASC, trades DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()


def confidence_bucket_rows(db: sqlite3.Connection) -> list[sqlite3.Row]:
    return db.execute(
        """
        SELECT CASE
                   WHEN confidence IS NULL THEN 'unknown'
                   WHEN confidence < 70 THEN '<70'
                   WHEN confidence < 80 THEN '70-79'
                   WHEN confidence < 90 THEN '80-89'
                   WHEN confidence < 95 THEN '90-94'
                   ELSE '95-100'
               END AS confidence_bucket,
               COUNT(*) AS trades,
               SUM(CASE WHEN result='WIN' THEN 1 ELSE 0 END) AS wins,
               SUM(CASE WHEN result='LOSS' THEN 1 ELSE 0 END) AS losses,
               SUM(CASE WHEN result='DRAW' THEN 1 ELSE 0 END) AS draws,
               ROUND(100.0 * SUM(CASE WHEN result='WIN' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) AS win_rate,
               SUM(COALESCE(profit_loss, 0)) AS profit_loss,
               AVG(COALESCE(profit_loss, 0)) AS avg_profit
        FROM external_trades
        GROUP BY confidence_bucket
        ORDER BY confidence_bucket
        """
    ).fetchall()


def hour_rows(db: sqlite3.Connection) -> list[sqlite3.Row]:
    return db.execute(
        """
        SELECT COALESCE(substr(entry_time, 12, 2), 'unknown') AS hour_utc,
               COUNT(*) AS trades,
               SUM(CASE WHEN result='WIN' THEN 1 ELSE 0 END) AS wins,
               SUM(CASE WHEN result='LOSS' THEN 1 ELSE 0 END) AS losses,
               SUM(CASE WHEN result='DRAW' THEN 1 ELSE 0 END) AS draws,
               ROUND(100.0 * SUM(CASE WHEN result='WIN' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 1) AS win_rate,
               SUM(COALESCE(profit_loss, 0)) AS profit_loss,
               AVG(COALESCE(profit_loss, 0)) AS avg_profit
        FROM external_trades
        GROUP BY hour_utc
        HAVING trades >= 3
        ORDER BY profit_loss DESC
        LIMIT 24
        """
    ).fetchall()


def dataset_rows(db: sqlite3.Connection) -> list[sqlite3.Row]:
    return db.execute(
        """
        SELECT d.id AS dataset_id,
               d.name AS dataset,
               d.trust_level AS trust_level,
               COUNT(t.id) AS trades,
               SUM(CASE WHEN t.result='WIN' THEN 1 ELSE 0 END) AS wins,
               SUM(CASE WHEN t.result='LOSS' THEN 1 ELSE 0 END) AS losses,
               SUM(CASE WHEN t.result='DRAW' THEN 1 ELSE 0 END) AS draws,
               ROUND(100.0 * SUM(CASE WHEN t.result='WIN' THEN 1 ELSE 0 END) / NULLIF(COUNT(t.id), 0), 1) AS win_rate,
               SUM(COALESCE(t.profit_loss, 0)) AS profit_loss
        FROM external_datasets d
        LEFT JOIN external_trades t ON t.dataset_id = d.id
        GROUP BY d.id, d.name, d.trust_level
        ORDER BY d.id
        """
    ).fetchall()


def print_findings(summary: sqlite3.Row) -> None:
    total = int(summary["total"] or 0)
    wins = int(summary["wins"] or 0)
    losses = int(summary["losses"] or 0)
    draws = int(summary["draws"] or 0)
    profit_loss = float(summary["profit_loss"] or 0)

    print_section("Initial interpretation")
    if total == 0:
        print("No external trades are available for analysis.")
        return

    print(f"Total external trades: {total}")
    print(f"Wins/Losses/Draws: {wins}/{losses}/{draws}")
    print(f"Win rate: {percent(wins, total)}")
    print(f"Profit/Loss: {profit_loss:.2f}")
    print(f"Average per trade: {money(summary['avg_profit'])}")
    print(f"Period: {summary['first_entry']} -> {summary['last_entry']}")
    print()

    if total < 1000:
        print("Warning: sample is still small. Treat results as research signals, not proof.")
    if profit_loss < 0:
        print("Warning: this imported strategy/dataset is negative as-is.")
    if losses > wins:
        print("Warning: losses are higher than wins; confidence scoring may need calibration.")
    print("Decision: do not enable automatic buying from this dataset alone.")


def main() -> int:
    print("=" * 72)
    print("QTB external trade analysis report")
    print("=" * 72)
    print(f"Database: {DB_PATH}")
    print("This report reads external_* research tables only. Native trades are not modified.")

    if not DB_PATH.exists():
        print("Database not found.")
        return 1

    with connect() as db:
        if not table_exists(db, "external_trades"):
            print("external_trades table not found. Import or initialize research tables first.")
            return 1

        summary = load_summary(db)
        print_findings(summary)

        print_rows(
            "Datasets",
            dataset_rows(db),
            ["dataset_id", "dataset", "trust_level", "trades", "wins", "losses", "draws", "win_rate", "profit_loss"],
        )
        print_rows(
            "Best assets by profit/loss",
            grouped_rows(db, "asset", "asset"),
            ["asset", "trades", "wins", "losses", "draws", "win_rate", "profit_loss", "avg_profit"],
        )
        print_rows(
            "Worst assets by profit/loss",
            grouped_rows_worst(db, "asset", "asset"),
            ["asset", "trades", "wins", "losses", "draws", "win_rate", "profit_loss", "avg_profit"],
        )
        print_rows(
            "Direction performance",
            grouped_rows(db, "direction", "direction"),
            ["direction", "trades", "wins", "losses", "draws", "win_rate", "profit_loss", "avg_profit"],
        )
        print_rows(
            "Confidence buckets",
            confidence_bucket_rows(db),
            ["confidence_bucket", "trades", "wins", "losses", "draws", "win_rate", "profit_loss", "avg_profit"],
        )
        print_rows(
            "Strategy performance",
            grouped_rows(db, "COALESCE(strategy_name, 'unknown')", "strategy"),
            ["strategy", "trades", "wins", "losses", "draws", "win_rate", "profit_loss", "avg_profit"],
        )
        print_rows(
            "UTC hour performance, minimum 3 trades",
            hour_rows(db),
            ["hour_utc", "trades", "wins", "losses", "draws", "win_rate", "profit_loss", "avg_profit"],
        )

    print("=" * 72)
    print("External analysis finished. No secrets were printed and no native trades were changed.")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
