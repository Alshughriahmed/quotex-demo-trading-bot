from __future__ import annotations

import argparse
import csv
import sqlite3
from datetime import datetime
from pathlib import Path


DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "data.db"
DEFAULT_EXPORT_DIR = Path(__file__).resolve().parents[1] / "exports"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export local DEMO trade records from data.db to a CSV file."
    )
    parser.add_argument(
        "--db",
        default=str(DEFAULT_DB_PATH),
        help="Path to local SQLite database. Defaults to bot/data.db.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional output CSV path. Defaults to bot/exports/trades_<timestamp>.csv.",
    )
    parser.add_argument(
        "--status",
        default=None,
        help="Optional trade status filter, for example CLOSED, ERROR, OPEN, or SCHEDULED.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optional maximum number of rows to export. 0 means all rows.",
    )
    return parser.parse_args()


def output_path(raw_output: str | None) -> Path:
    if raw_output:
        return Path(raw_output).expanduser().resolve()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return DEFAULT_EXPORT_DIR / f"trades_{timestamp}.csv"


def connect(db_path: Path) -> sqlite3.Connection:
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection


def table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    row = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def trade_columns(connection: sqlite3.Connection) -> list[str]:
    rows = connection.execute("PRAGMA table_info(trades)").fetchall()
    return [row["name"] for row in rows]


def fetch_trades(connection: sqlite3.Connection, status: str | None, limit: int) -> tuple[list[str], list[sqlite3.Row]]:
    columns = trade_columns(connection)
    if not columns:
        return [], []

    sql = "SELECT * FROM trades"
    params: list[object] = []
    if status:
        sql += " WHERE UPPER(status) = UPPER(?)"
        params.append(status)
    sql += " ORDER BY COALESCE(entry_time, signal_time, created_at) DESC, id DESC"
    if limit and limit > 0:
        sql += " LIMIT ?"
        params.append(limit)

    rows = connection.execute(sql, params).fetchall()
    return columns, rows


def write_csv(path: Path, columns: list[str], rows: list[sqlite3.Row]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row[column] for column in columns})


def main() -> int:
    args = parse_args()
    db_path = Path(args.db).expanduser().resolve()
    csv_path = output_path(args.output)

    with connect(db_path) as connection:
        if not table_exists(connection, "trades"):
            raise RuntimeError("The local database does not contain a trades table yet.")
        columns, rows = fetch_trades(connection, args.status, args.limit)

    write_csv(csv_path, columns, rows)
    print(f"Exported {len(rows)} trade rows to: {csv_path}")
    if len(rows) == 0:
        print("No matching trades were found yet. Start the DEMO scanner and collect records first.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
