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
    row = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,)).fetchone()
    return row is not None


def scalar(db: sqlite3.Connection, query: str, params: tuple[Any, ...] = ()) -> Any:
    row = db.execute(query, params).fetchone()
    return row[0] if row else None


def print_section(title: str) -> None:
    print("-" * 72)
    print(title)
    print("-" * 72)


def pct(wins: int, total: int) -> str:
    return f"{(wins / total * 100):.1f}%" if total else "0.0%"


def format_value(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.2f}"
    if value is None:
        return ""
    return str(value)


def print_rows(title: str, rows: list[sqlite3.Row], columns: list[str]) -> None:
    print_section(title)
    if not rows:
        print("No data.")
        return
    print(" | ".join(columns))
    print(" | ".join("-" * len(column) for column in columns))
    for row in rows:
        print(" | ".join(format_value(row[column]) for column in columns))


def dataset_summary(db: sqlite3.Connection) -> list[sqlite3.Row]:
    return db.execute(
        """
        SELECT d.id AS dataset_id,
               d.name AS dataset,
               d.detected_format AS format,
               COUNT(t.id) AS trades,
               SUM(CASE WHEN t.result='WIN' THEN 1 ELSE 0 END) AS wins,
               SUM(CASE WHEN t.result='LOSS' THEN 1 ELSE 0 END) AS losses,
               SUM(CASE WHEN t.result='DRAW' THEN 1 ELSE 0 END) AS draws,
               ROUND(100.0 * SUM(CASE WHEN t.result='WIN' THEN 1 ELSE 0 END) /
                    NULLIF(SUM(CASE WHEN t.result IN ('WIN','LOSS','DRAW') THEN 1 ELSE 0 END), 0), 1) AS win_rate,
               ROUND(SUM(COALESCE(t.profit_loss, 0)), 2) AS profit_loss,
               MIN(t.entry_time) AS first_entry,
               MAX(t.entry_time) AS last_entry
        FROM external_datasets d
        LEFT JOIN external_trades t ON t.dataset_id = d.id
        GROUP BY d.id, d.name, d.detected_format
        ORDER BY d.id
        """
    ).fetchall()


def latest_dataset_id(db: sqlite3.Connection) -> int | None:
    value = scalar(db, "SELECT MAX(id) FROM external_datasets")
    return int(value) if value is not None else None


def performance_by_asset(db: sqlite3.Connection, dataset_id: int, best: bool) -> list[sqlite3.Row]:
    direction = "DESC" if best else "ASC"
    return db.execute(
        f"""
        SELECT asset,
               COUNT(*) AS trades,
               SUM(CASE WHEN result='WIN' THEN 1 ELSE 0 END) AS wins,
               SUM(CASE WHEN result='LOSS' THEN 1 ELSE 0 END) AS losses,
               SUM(CASE WHEN result='DRAW' THEN 1 ELSE 0 END) AS draws,
               ROUND(100.0 * SUM(CASE WHEN result='WIN' THEN 1 ELSE 0 END) /
                    NULLIF(SUM(CASE WHEN result IN ('WIN','LOSS','DRAW') THEN 1 ELSE 0 END), 0), 1) AS win_rate,
               ROUND(SUM(COALESCE(profit_loss, 0)), 2) AS profit_loss,
               ROUND(AVG(COALESCE(profit_loss, 0)), 2) AS avg_profit
        FROM external_trades
        WHERE dataset_id = ?
        GROUP BY asset
        HAVING trades >= 3
        ORDER BY profit_loss {direction}, trades DESC
        LIMIT 15
        """,
        (dataset_id,),
    ).fetchall()


def performance_by_direction(db: sqlite3.Connection, dataset_id: int) -> list[sqlite3.Row]:
    return db.execute(
        """
        SELECT direction,
               COUNT(*) AS trades,
               SUM(CASE WHEN result='WIN' THEN 1 ELSE 0 END) AS wins,
               SUM(CASE WHEN result='LOSS' THEN 1 ELSE 0 END) AS losses,
               SUM(CASE WHEN result='DRAW' THEN 1 ELSE 0 END) AS draws,
               ROUND(100.0 * SUM(CASE WHEN result='WIN' THEN 1 ELSE 0 END) /
                    NULLIF(SUM(CASE WHEN result IN ('WIN','LOSS','DRAW') THEN 1 ELSE 0 END), 0), 1) AS win_rate,
               ROUND(SUM(COALESCE(profit_loss, 0)), 2) AS profit_loss,
               ROUND(AVG(COALESCE(profit_loss, 0)), 2) AS avg_profit
        FROM external_trades
        WHERE dataset_id = ?
        GROUP BY direction
        ORDER BY profit_loss DESC
        """,
        (dataset_id,),
    ).fetchall()


def performance_by_confidence(db: sqlite3.Connection, dataset_id: int) -> list[sqlite3.Row]:
    return db.execute(
        """
        SELECT CASE
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
               ROUND(100.0 * SUM(CASE WHEN result='WIN' THEN 1 ELSE 0 END) /
                    NULLIF(SUM(CASE WHEN result IN ('WIN','LOSS','DRAW') THEN 1 ELSE 0 END), 0), 1) AS win_rate,
               ROUND(SUM(COALESCE(profit_loss, 0)), 2) AS profit_loss,
               ROUND(AVG(COALESCE(profit_loss, 0)), 2) AS avg_profit
        FROM external_trades
        WHERE dataset_id = ?
        GROUP BY confidence_bucket
        ORDER BY confidence_bucket
        """,
        (dataset_id,),
    ).fetchall()


def performance_by_hour(db: sqlite3.Connection, dataset_id: int) -> list[sqlite3.Row]:
    return db.execute(
        """
        SELECT strftime('%H', entry_time) AS hour_utc,
               COUNT(*) AS trades,
               SUM(CASE WHEN result='WIN' THEN 1 ELSE 0 END) AS wins,
               SUM(CASE WHEN result='LOSS' THEN 1 ELSE 0 END) AS losses,
               SUM(CASE WHEN result='DRAW' THEN 1 ELSE 0 END) AS draws,
               ROUND(100.0 * SUM(CASE WHEN result='WIN' THEN 1 ELSE 0 END) /
                    NULLIF(SUM(CASE WHEN result IN ('WIN','LOSS','DRAW') THEN 1 ELSE 0 END), 0), 1) AS win_rate,
               ROUND(SUM(COALESCE(profit_loss, 0)), 2) AS profit_loss,
               ROUND(AVG(COALESCE(profit_loss, 0)), 2) AS avg_profit
        FROM external_trades
        WHERE dataset_id = ?
        GROUP BY hour_utc
        HAVING trades >= 5
        ORDER BY profit_loss DESC
        LIMIT 24
        """,
        (dataset_id,),
    ).fetchall()


def overlap_report(db: sqlite3.Connection) -> None:
    dataset_ids = [int(row[0]) for row in db.execute("SELECT id FROM external_datasets ORDER BY id").fetchall()]
    if len(dataset_ids) < 2:
        print_section("Dataset overlap estimate")
        print("Need at least two datasets to estimate overlap.")
        return

    latest = max(dataset_ids)
    previous = [dataset_id for dataset_id in dataset_ids if dataset_id != latest]
    placeholders = ",".join("?" for _ in previous)
    params: tuple[Any, ...] = (latest, *previous)
    duplicate_like = int(
        scalar(
            db,
            f"""
            SELECT COUNT(*)
            FROM external_trades t2
            WHERE t2.dataset_id = ?
              AND EXISTS (
                  SELECT 1
                  FROM external_trades t1
                  WHERE t1.dataset_id IN ({placeholders})
                    AND COALESCE(t1.asset, '') = COALESCE(t2.asset, '')
                    AND COALESCE(t1.direction, '') = COALESCE(t2.direction, '')
                    AND COALESCE(t1.entry_time, '') = COALESCE(t2.entry_time, '')
                    AND COALESCE(t1.expiry_time, '') = COALESCE(t2.expiry_time, '')
                    AND COALESCE(t1.result, '') = COALESCE(t2.result, '')
              )
            """,
            params,
        )
        or 0
    )
    latest_total = int(scalar(db, "SELECT COUNT(*) FROM external_trades WHERE dataset_id=?", (latest,)) or 0)
    unique_like = max(0, latest_total - duplicate_like)

    print_section("Dataset overlap estimate")
    print(f"Latest dataset id: {latest}")
    print(f"Latest dataset trades: {latest_total}")
    print(f"Duplicate-like trades already seen in older datasets: {duplicate_like}")
    print(f"New/incremental-like trades in latest dataset: {unique_like}")
    print("Note: this is an estimate based on asset/direction/entry/expiry/result, not a broker order id.")


def main() -> int:
    print("=" * 72)
    print("QTB external dataset drilldown report")
    print("=" * 72)
    print("This reads external_* research tables only. Native trades are not modified.")
    print(f"Database: {DB_PATH}")

    if not DB_PATH.exists():
        print("Database not found.")
        return 1

    with connect() as db:
        missing = [table for table in ("external_datasets", "external_trades") if not table_exists(db, table)]
        if missing:
            print(f"Missing external tables: {', '.join(missing)}")
            return 1

        rows = dataset_summary(db)
        print_rows(
            "Dataset summary",
            rows,
            ["dataset_id", "dataset", "format", "trades", "wins", "losses", "draws", "win_rate", "profit_loss", "first_entry", "last_entry"],
        )
        overlap_report(db)

        latest = latest_dataset_id(db)
        if latest is None:
            print("No external datasets found.")
            return 0

        print_section("Latest dataset decision")
        latest_row = [row for row in rows if int(row["dataset_id"]) == latest][0]
        print(f"Latest dataset: {latest_row['dataset']} (id={latest})")
        print(f"Trades: {latest_row['trades']}, win rate: {latest_row['win_rate']}%, profit/loss: {latest_row['profit_loss']}")
        print("Do not enable automatic buying from this dataset as-is. Use it only for research and filter discovery.")

        print_rows("Latest dataset - best assets, min 3 trades", performance_by_asset(db, latest, True), ["asset", "trades", "wins", "losses", "draws", "win_rate", "profit_loss", "avg_profit"])
        print_rows("Latest dataset - worst assets, min 3 trades", performance_by_asset(db, latest, False), ["asset", "trades", "wins", "losses", "draws", "win_rate", "profit_loss", "avg_profit"])
        print_rows("Latest dataset - direction", performance_by_direction(db, latest), ["direction", "trades", "wins", "losses", "draws", "win_rate", "profit_loss", "avg_profit"])
        print_rows("Latest dataset - confidence buckets", performance_by_confidence(db, latest), ["confidence_bucket", "trades", "wins", "losses", "draws", "win_rate", "profit_loss", "avg_profit"])
        print_rows("Latest dataset - UTC hour, min 5 trades", performance_by_hour(db, latest), ["hour_utc", "trades", "wins", "losses", "draws", "win_rate", "profit_loss", "avg_profit"])

    print("=" * 72)
    print("External dataset drilldown finished. No secrets were printed and no native trades were changed.")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
