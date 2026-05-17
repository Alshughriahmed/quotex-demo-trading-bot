from __future__ import annotations

import sqlite3
from pathlib import Path


BOT_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BOT_DIR / "data.db"


def main() -> int:
    if not DB_PATH.exists():
        print(f"Database not found: {DB_PATH}")
        return 1

    with sqlite3.connect(DB_PATH) as connection:
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
        connection.execute(
            """
            INSERT INTO bot_settings(key, value, value_type, description)
            VALUES ('auto_buy_enabled', 'false', 'bool', 'Allow automatic DEMO order placement')
            ON CONFLICT(key) DO UPDATE SET
                value = 'false',
                value_type = 'bool',
                description = 'Allow automatic DEMO order placement',
                updated_at = CURRENT_TIMESTAMP
            """
        )
        connection.commit()

    print("auto_buy_enabled=false")
    print("Automatic DEMO order placement is disabled locally.")
    print("This does not affect Telegram test messages or CSV/data reports.")
    print("No secrets were printed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
