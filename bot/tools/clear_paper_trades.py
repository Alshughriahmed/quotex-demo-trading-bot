from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


BOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = BOT_DIR / "data.db"
PAPER_STRATEGY = "paper_simulated_v1"
PAPER_REASON_PREFIX = "SIMULATED PAPER DATA"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Delete only locally generated paper/simulated trade records."
    )
    parser.add_argument(
        "--db",
        default=str(DEFAULT_DB_PATH),
        help="Path to local SQLite database. Defaults to bot/data.db.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Actually delete matching paper records. Without this flag, only prints counts.",
    )
    return parser.parse_args()


def table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    row = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def count_all(connection: sqlite3.Connection) -> int:
    row = connection.execute("SELECT COUNT(*) FROM trades").fetchone()
    return int(row[0] or 0)


def count_paper(connection: sqlite3.Connection) -> int:
    row = connection.execute(
        """
        SELECT COUNT(*)
        FROM trades
        WHERE strategy_name = ?
           OR decision_reason LIKE ?
        """,
        (PAPER_STRATEGY, f"{PAPER_REASON_PREFIX}%"),
    ).fetchone()
    return int(row[0] or 0)


def delete_paper(connection: sqlite3.Connection) -> int:
    cursor = connection.execute(
        """
        DELETE FROM trades
        WHERE strategy_name = ?
           OR decision_reason LIKE ?
        """,
        (PAPER_STRATEGY, f"{PAPER_REASON_PREFIX}%"),
    )
    return int(cursor.rowcount or 0)


def main() -> int:
    args = parse_args()
    db_path = Path(args.db).expanduser().resolve()

    if not db_path.exists():
        print(f"Database not found: {db_path}")
        return 1

    with sqlite3.connect(db_path) as connection:
        if not table_exists(connection, "trades"):
            print("The database does not contain a trades table.")
            return 1

        total_before = count_all(connection)
        paper_before = count_paper(connection)

        print(f"Database: {db_path}")
        print(f"Total trades before: {total_before}")
        print(f"Paper/simulated trades found: {paper_before}")

        if not args.yes:
            print("Dry run only. Add --yes to delete paper/simulated records.")
            return 0

        deleted = delete_paper(connection)
        connection.commit()
        total_after = count_all(connection)

    print(f"Deleted paper/simulated trades: {deleted}")
    print(f"Total trades after: {total_after}")
    print("Only locally generated paper records were targeted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
