from __future__ import annotations

import sqlite3
from pathlib import Path


BOT_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BOT_DIR / "data.db"


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_tables(db: sqlite3.Connection) -> None:
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS research_market_candles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_key TEXT NOT NULL,
            asset TEXT NOT NULL,
            timeframe_seconds INTEGER NOT NULL,
            candle_time TEXT NOT NULL,
            open REAL NOT NULL,
            high REAL NOT NULL,
            low REAL NOT NULL,
            close REAL NOT NULL,
            volume REAL,
            is_closed INTEGER NOT NULL DEFAULT 1,
            raw_json TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(source_key, asset, timeframe_seconds, candle_time)
        );

        CREATE TABLE IF NOT EXISTS research_strategy_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            strategy_name TEXT NOT NULL,
            strategy_version TEXT,
            source_key TEXT NOT NULL,
            timeframe_seconds INTEGER NOT NULL,
            settings_json TEXT,
            notes TEXT,
            started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            finished_at TEXT,
            status TEXT NOT NULL DEFAULT 'OPEN'
        );

        CREATE TABLE IF NOT EXISTS research_signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER,
            source_key TEXT NOT NULL,
            strategy_name TEXT NOT NULL,
            strategy_version TEXT,
            asset TEXT NOT NULL,
            direction TEXT NOT NULL CHECK(direction IN ('CALL', 'PUT', 'NO_TRADE')),
            signal_time TEXT NOT NULL,
            entry_time TEXT,
            expiry_time TEXT,
            duration_seconds INTEGER NOT NULL,
            confidence REAL NOT NULL DEFAULT 0,
            rsi REAL,
            ema_fast REAL,
            ema_slow REAL,
            ema_gap REAL,
            adx REAL,
            atr REAL,
            volatility REAL,
            candle_body_ratio REAL,
            payout REAL,
            reason TEXT,
            indicators_json TEXT,
            candles_ref_json TEXT,
            data_quality TEXT NOT NULL DEFAULT 'unreviewed',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(run_id) REFERENCES research_strategy_runs(id)
        );

        CREATE TABLE IF NOT EXISTS research_signal_outcomes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            signal_id INTEGER NOT NULL UNIQUE,
            outcome_time TEXT NOT NULL,
            entry_price REAL,
            exit_price REAL,
            result TEXT NOT NULL CHECK(result IN ('WIN', 'LOSS', 'DRAW', 'UNKNOWN')),
            theoretical_profit_loss REAL,
            payout REAL,
            evaluation_method TEXT NOT NULL DEFAULT 'price_comparison',
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(signal_id) REFERENCES research_signals(id)
        );

        CREATE TABLE IF NOT EXISTS research_analysis_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            input_scope TEXT,
            result_summary_json TEXT,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_research_candles_asset_time
            ON research_market_candles(asset, timeframe_seconds, candle_time);
        CREATE INDEX IF NOT EXISTS idx_research_signals_asset_time
            ON research_signals(asset, signal_time);
        CREATE INDEX IF NOT EXISTS idx_research_signals_strategy
            ON research_signals(strategy_name, strategy_version);
        CREATE INDEX IF NOT EXISTS idx_research_outcomes_result
            ON research_signal_outcomes(result);
        """
    )


def table_count(db: sqlite3.Connection, table_name: str) -> int:
    row = db.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
    return int(row[0] or 0)


def main() -> int:
    print("=" * 72)
    print("QTB signal-only research tables initializer")
    print("=" * 72)
    print(f"Database: {DB_PATH}")
    print("This creates research_* tables only. It does not trade or start the bot.")

    with connect() as db:
        db.execute("PRAGMA foreign_keys = ON")
        init_tables(db)
        db.commit()

        tables = [
            "research_market_candles",
            "research_strategy_runs",
            "research_signals",
            "research_signal_outcomes",
            "research_analysis_runs",
        ]
        print("Research tables:")
        for table in tables:
            print(f"- {table}: {table_count(db, table)} rows")

    print("=" * 72)
    print("Signal-only research tables are ready.")
    print("No native trades were changed and no secrets were printed.")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
