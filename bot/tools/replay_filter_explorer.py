from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

BOT_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BOT_DIR / "data.db"


def connect() -> sqlite3.Connection:
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    return db


def table_exists(db: sqlite3.Connection, name: str) -> bool:
    return db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None


def fmt(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def section(title: str) -> None:
    print("-" * 72)
    print(title)
    print("-" * 72)


def print_rows(title: str, rows: list[sqlite3.Row], cols: list[str]) -> None:
    section(title)
    if not rows:
        print("No data.")
        return
    print(" | ".join(cols))
    print(" | ".join("-" * len(c) for c in cols))
    for row in rows:
        print(" | ".join(fmt(row[c]) for c in cols))


def grouped(db: sqlite3.Connection, expr: str, alias: str, min_trades: int, order_sql: str, limit: int = 30) -> list[sqlite3.Row]:
    return db.execute(
        f"""
        SELECT {expr} AS {alias},
               COUNT(*) AS trades,
               SUM(CASE WHEN o.result='WIN' THEN 1 ELSE 0 END) AS wins,
               SUM(CASE WHEN o.result='LOSS' THEN 1 ELSE 0 END) AS losses,
               SUM(CASE WHEN o.result='DRAW' THEN 1 ELSE 0 END) AS draws,
               ROUND(100.0 * SUM(CASE WHEN o.result='WIN' THEN 1 ELSE 0 END) /
                    NULLIF(SUM(CASE WHEN o.result IN ('WIN','LOSS','DRAW') THEN 1 ELSE 0 END), 0), 1) AS win_rate,
               ROUND(SUM(COALESCE(o.theoretical_profit_loss, 0)), 2) AS profit_loss,
               ROUND(AVG(COALESCE(o.theoretical_profit_loss, 0)), 3) AS avg_profit
        FROM research_signals s
        JOIN research_signal_outcomes o ON o.signal_id = s.id
        WHERE s.direction IN ('CALL','PUT')
        GROUP BY {alias}
        HAVING trades >= ?
        ORDER BY {order_sql}
        LIMIT ?
        """,
        (min_trades, limit),
    ).fetchall()


def grouped_two(db: sqlite3.Connection, expr1: str, alias1: str, expr2: str, alias2: str, min_trades: int, order_sql: str, limit: int = 30) -> list[sqlite3.Row]:
    return db.execute(
        f"""
        SELECT {expr1} AS {alias1},
               {expr2} AS {alias2},
               COUNT(*) AS trades,
               SUM(CASE WHEN o.result='WIN' THEN 1 ELSE 0 END) AS wins,
               SUM(CASE WHEN o.result='LOSS' THEN 1 ELSE 0 END) AS losses,
               SUM(CASE WHEN o.result='DRAW' THEN 1 ELSE 0 END) AS draws,
               ROUND(100.0 * SUM(CASE WHEN o.result='WIN' THEN 1 ELSE 0 END) /
                    NULLIF(SUM(CASE WHEN o.result IN ('WIN','LOSS','DRAW') THEN 1 ELSE 0 END), 0), 1) AS win_rate,
               ROUND(SUM(COALESCE(o.theoretical_profit_loss, 0)), 2) AS profit_loss,
               ROUND(AVG(COALESCE(o.theoretical_profit_loss, 0)), 3) AS avg_profit
        FROM research_signals s
        JOIN research_signal_outcomes o ON o.signal_id = s.id
        WHERE s.direction IN ('CALL','PUT')
        GROUP BY {alias1}, {alias2}
        HAVING trades >= ?
        ORDER BY {order_sql}
        LIMIT ?
        """,
        (min_trades, limit),
    ).fetchall()


def scoped_metrics(db: sqlite3.Connection, name: str, where_sql: str = "1=1", params: tuple[Any, ...] = ()) -> sqlite3.Row:
    return db.execute(
        f"""
        SELECT ? AS filter_name,
               COUNT(*) AS trades,
               SUM(CASE WHEN o.result='WIN' THEN 1 ELSE 0 END) AS wins,
               SUM(CASE WHEN o.result='LOSS' THEN 1 ELSE 0 END) AS losses,
               SUM(CASE WHEN o.result='DRAW' THEN 1 ELSE 0 END) AS draws,
               ROUND(100.0 * SUM(CASE WHEN o.result='WIN' THEN 1 ELSE 0 END) /
                    NULLIF(SUM(CASE WHEN o.result IN ('WIN','LOSS','DRAW') THEN 1 ELSE 0 END), 0), 1) AS win_rate,
               ROUND(SUM(COALESCE(o.theoretical_profit_loss, 0)), 2) AS profit_loss,
               ROUND(AVG(COALESCE(o.theoretical_profit_loss, 0)), 3) AS avg_profit
        FROM research_signals s
        JOIN research_signal_outcomes o ON o.signal_id = s.id
        WHERE s.direction IN ('CALL','PUT') AND {where_sql}
        """,
        (name, *params),
    ).fetchone()


def main() -> int:
    print("=" * 72)
    print("QTB replay filter explorer")
    print("=" * 72)
    print("This explores evaluated replay research signals only. It does not trade or modify native trades.")
    print(f"Database: {DB_PATH}")

    if not DB_PATH.exists():
        print("Database not found.")
        return 1

    with connect() as db:
        missing = [name for name in ("research_signals", "research_signal_outcomes") if not table_exists(db, name)]
        if missing:
            print(f"Missing research tables: {', '.join(missing)}")
            return 1

        total = int(db.execute("SELECT COUNT(*) FROM research_signal_outcomes").fetchone()[0] or 0)
        if total == 0:
            print("No evaluated replay outcomes found yet.")
            return 0

        cols = ["filter_name", "trades", "wins", "losses", "draws", "win_rate", "profit_loss", "avg_profit"]
        scenarios = [
            scoped_metrics(db, "baseline_all_replay"),
            scoped_metrics(db, "only_put", "s.direction='PUT'"),
            scoped_metrics(db, "only_call", "s.direction='CALL'"),
            scoped_metrics(db, "exclude_hours_12_17", "strftime('%H', COALESCE(s.entry_time, s.signal_time)) NOT IN ('12','17')"),
            scoped_metrics(db, "only_hours_15_08_09", "strftime('%H', COALESCE(s.entry_time, s.signal_time)) IN ('15','08','09')"),
            scoped_metrics(db, "only_put_exclude_12_17", "s.direction='PUT' AND strftime('%H', COALESCE(s.entry_time, s.signal_time)) NOT IN ('12','17')"),
            scoped_metrics(db, "only_call_exclude_12_17", "s.direction='CALL' AND strftime('%H', COALESCE(s.entry_time, s.signal_time)) NOT IN ('12','17')"),
        ]
        print_rows("Replay scenario comparison", scenarios, cols)

        common_cols = ["direction", "trades", "wins", "losses", "draws", "win_rate", "profit_loss", "avg_profit"]
        print_rows("By direction", grouped(db, "s.direction", "direction", 10, "profit_loss DESC"), common_cols)
        print_rows("Best UTC hours, min 20 trades", grouped(db, "strftime('%H', COALESCE(s.entry_time, s.signal_time))", "hour_utc", 20, "profit_loss DESC"), ["hour_utc", "trades", "wins", "losses", "draws", "win_rate", "profit_loss", "avg_profit"])
        print_rows("Worst UTC hours, min 20 trades", grouped(db, "strftime('%H', COALESCE(s.entry_time, s.signal_time))", "hour_utc", 20, "profit_loss ASC"), ["hour_utc", "trades", "wins", "losses", "draws", "win_rate", "profit_loss", "avg_profit"])
        print_rows("Best direction + UTC hour, min 20 trades", grouped_two(db, "s.direction", "direction", "strftime('%H', COALESCE(s.entry_time, s.signal_time))", "hour_utc", 20, "profit_loss DESC"), ["direction", "hour_utc", "trades", "wins", "losses", "draws", "win_rate", "profit_loss", "avg_profit"])
        print_rows("Worst direction + UTC hour, min 20 trades", grouped_two(db, "s.direction", "direction", "strftime('%H', COALESCE(s.entry_time, s.signal_time))", "hour_utc", 20, "profit_loss ASC"), ["direction", "hour_utc", "trades", "wins", "losses", "draws", "win_rate", "profit_loss", "avg_profit"])
        print_rows("Confidence buckets", grouped(db, "CASE WHEN s.confidence < 70 THEN '<70' WHEN s.confidence < 80 THEN '70-79' WHEN s.confidence < 90 THEN '80-89' WHEN s.confidence < 95 THEN '90-94' ELSE '95-100' END", "confidence_bucket", 1, "confidence_bucket"), ["confidence_bucket", "trades", "wins", "losses", "draws", "win_rate", "profit_loss", "avg_profit"])

        section("Decision")
        print("Treat any positive group as a research hypothesis only.")
        print("A group is interesting only if it has enough trades and survives chronological validation on newer data.")
        print("Next step: run replay validation on more months and more pairs before changing any strategy logic.")

    print("=" * 72)
    print("Replay filter explorer finished. No native trades were changed.")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
