from __future__ import annotations

import sqlite3
from pathlib import Path


BOT_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BOT_DIR / "data.db"


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    row = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


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


def get_setting(connection: sqlite3.Connection, key: str, default: str = "false") -> str:
    if not table_exists(connection, "bot_settings"):
        return default
    row = connection.execute("SELECT value FROM bot_settings WHERE key = ?", (key,)).fetchone()
    return str(row["value"]) if row else default


def set_setting(connection: sqlite3.Connection, key: str, value: str, value_type: str = "bool", description: str = "") -> None:
    connection.execute(
        """
        INSERT INTO bot_settings(key, value, value_type, description)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET
            value = excluded.value,
            value_type = excluded.value_type,
            description = excluded.description,
            updated_at = CURRENT_TIMESTAMP
        """,
        (key, value, value_type, description),
    )


def market_source_status(connection: sqlite3.Connection) -> tuple[str, str]:
    if not table_exists(connection, "quotex_accounts"):
        return "MISSING", "quotex_accounts table is missing"

    row = connection.execute(
        "SELECT email, password, account_type, enabled FROM quotex_accounts WHERE id = 1"
    ).fetchone()
    if not row:
        return "MISSING", "local Quotex account row is missing"

    has_email = bool(row["email"])
    has_password = bool(row["password"])
    enabled = int(row["enabled"] or 0) == 1
    account_type = str(row["account_type"] or "DEMO")

    if has_email and has_password and enabled:
        return "CONFIGURED", f"configured, account_type={account_type}"
    if has_email and has_password and not enabled:
        return "DISABLED", f"values exist but account is disabled, account_type={account_type}"
    return "MISSING", "local Quotex source is not configured"


def main() -> int:
    if not DB_PATH.exists():
        print(f"Database not found: {DB_PATH}")
        return 1

    with connect() as connection:
        ensure_settings_table(connection)
        scanner_before = get_setting(connection, "bot_enabled", "false").lower()
        source_status, source_detail = market_source_status(connection)

        print(f"Database: {DB_PATH}")
        print(f"Scanner before: {'RUNNING' if scanner_before == 'true' else 'STOPPED'}")
        print(f"Market data source: {source_status}")
        print(f"Source detail: {source_detail}")

        if source_status != "CONFIGURED" and scanner_before == "true":
            set_setting(
                connection,
                "bot_enabled",
                "false",
                "bool",
                "تشغيل أو إيقاف البوت",
            )
            connection.commit()
            print("Action: scanner was forced to STOPPED because market data source is not configured.")
        elif source_status != "CONFIGURED":
            print("Action: no change needed; scanner is already stopped or source is not ready.")
        else:
            print("Action: no change needed; market data source is configured.")

        scanner_after = get_setting(connection, "bot_enabled", "false").lower()
        print(f"Scanner after: {'RUNNING' if scanner_after == 'true' else 'STOPPED'}")

    print("No secrets were printed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
