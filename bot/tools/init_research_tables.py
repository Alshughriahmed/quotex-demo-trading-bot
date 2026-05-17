from __future__ import annotations

import sqlite3
from pathlib import Path


BOT_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BOT_DIR / "data.db"


def main() -> int:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS external_datasets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                source_description TEXT,
                detected_format TEXT,
                original_path TEXT,
                trust_level TEXT NOT NULL DEFAULT 'unknown',
                notes TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS external_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                dataset_id INTEGER,
                asset TEXT,
                direction TEXT,
                signal_time TEXT,
                entry_time TEXT,
                expiry_time TEXT,
                duration_seconds INTEGER,
                confidence REAL,
                amount REAL,
                result TEXT,
                profit_loss REAL,
                entry_price REAL,
                exit_price REAL,
                payout REAL,
                strategy_name TEXT,
                decision_reason TEXT,
                raw_row_json TEXT,
                data_quality TEXT NOT NULL DEFAULT 'unreviewed',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(dataset_id) REFERENCES external_datasets(id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS external_strategies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                dataset_id INTEGER,
                name TEXT,
                description TEXT,
                source_file TEXT,
                raw_text TEXT,
                notes TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(dataset_id) REFERENCES external_datasets(id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS external_import_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                dataset_id INTEGER,
                level TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(dataset_id) REFERENCES external_datasets(id)
            )
            """
        )
        connection.commit()

    print(f"Research tables initialized in: {DB_PATH}")
    print("Created/verified: external_datasets, external_trades, external_strategies, external_import_logs")
    print("No secrets were printed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
