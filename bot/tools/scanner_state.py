from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


BOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = BOT_DIR / "data.db"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read or change the local DEMO scanner state.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--status", action="store_true", help="Print scanner status.")
    group.add_argument("--start", action="store_true", help="Set bot_enabled=true.")
    group.add_argument("--stop", action="store_true", help="Set bot_enabled=false.")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="Path to local SQLite database.")
    return parser.parse_args()


def ensure_settings_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS bot_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            value_type TEXT NOT NULL DEFAULT 'text',
            description TEXT,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def get_value(connection: sqlite3.Connection, key: str, default: str = "false") -> str:
    row = connection.execute("SELECT value FROM bot_settings WHERE key = ?", (key,)).fetchone()
    return str(row[0]) if row else default


def set_value(connection: sqlite3.Connection, key: str, value: str) -> None:
    connection.execute(
        """
        INSERT INTO bot_settings(key, value, value_type, description)
        VALUES (?, ?, 'bool', 'تشغيل أو إيقاف البوت')
        ON CONFLICT(key) DO UPDATE SET
            value = excluded.value,
            updated_at = CURRENT_TIMESTAMP
        """,
        (key, value),
    )


def print_status(connection: sqlite3.Connection) -> None:
    value = get_value(connection, "bot_enabled", "false").lower()
    label = "RUNNING" if value == "true" else "STOPPED"
    print(f"DEMO scanner status: {label}")
    print(f"bot_enabled={value}")


def main() -> int:
    args = parse_args()
    db_path = Path(args.db).expanduser().resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as connection:
        ensure_settings_table(connection)
        if args.start:
            set_value(connection, "bot_enabled", "true")
            connection.commit()
            print("DEMO scanner was set to RUNNING.")
        elif args.stop:
            set_value(connection, "bot_enabled", "false")
            connection.commit()
            print("DEMO scanner was set to STOPPED.")
        print_status(connection)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
