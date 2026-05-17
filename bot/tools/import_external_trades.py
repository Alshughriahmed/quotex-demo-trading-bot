from __future__ import annotations

import argparse
import json
import sqlite3
import zipfile
from pathlib import Path


BOT_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BOT_DIR / "data.db"
INBOX_DIR = BOT_DIR / "external_inputs"
WORK_DIR = BOT_DIR / "extracted_external" / "_import_work"
SOURCE_DB_PATH = WORK_DIR / "source.db"

TRADE_MAP = [
    "asset",
    "direction",
    "signal_time",
    "entry_time",
    "expiry_time",
    "duration_seconds",
    "confidence",
    "amount",
    "result",
    "profit_loss",
    "entry_price",
    "exit_price",
    "payout",
    "strategy_name",
    "decision_reason",
]

RAW_KEEP = [
    "account_type",
    "rsi",
    "ema_fast",
    "ema_slow",
    "ema_gap",
    "adx",
    "atr",
    "market_session",
    "status",
    "error_message",
    "created_at",
    "updated_at",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import external demo-bot trades into external_* tables.")
    parser.add_argument("archive", nargs="?", help="Zip file name or path. Defaults to newest zip in bot/external_inputs.")
    parser.add_argument("--yes", action="store_true", help="Actually import. Without this flag, only dry-run summary is printed.")
    parser.add_argument("--force", action="store_true", help="Allow importing the same archive path again.")
    return parser.parse_args()


def resolve_archive(raw: str | None) -> Path:
    if raw:
        path = Path(raw).expanduser()
        if not path.is_absolute():
            path = INBOX_DIR / path
    else:
        zips = sorted(INBOX_DIR.glob("*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not zips:
            raise FileNotFoundError(f"No zip file found in {INBOX_DIR}")
        path = zips[0]
    path = path.resolve()
    if path.suffix.lower() != ".zip":
        raise ValueError("Only .zip is supported.")
    return path


def prepare_source_db(zf: zipfile.ZipFile, db_name: str) -> Path:
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    cleanup_source_db()
    SOURCE_DB_PATH.write_bytes(zf.read(db_name))
    return SOURCE_DB_PATH


def cleanup_source_db() -> None:
    try:
        SOURCE_DB_PATH.unlink(missing_ok=True)
    except OSError:
        pass


def init_tables(db: sqlite3.Connection) -> None:
    db.executescript(
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
        );
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
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS external_strategies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dataset_id INTEGER,
            name TEXT,
            description TEXT,
            source_file TEXT,
            raw_text TEXT,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS external_import_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dataset_id INTEGER,
            level TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """
    )


def find_db(zf: zipfile.ZipFile) -> str | None:
    names = [n for n in zf.namelist() if n.lower().endswith(".db")]
    if "bot/data.db" in names:
        return "bot/data.db"
    return names[0] if names else None


def connect_readonly(path: Path) -> sqlite3.Connection:
    uri = path.resolve().as_uri() + "?mode=ro&immutable=1"
    return sqlite3.connect(uri, uri=True)


def summary(source_db: Path) -> dict:
    db = connect_readonly(source_db)
    try:
        db.row_factory = sqlite3.Row
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "trades" not in tables:
            return {"total": 0}
        row = db.execute(
            """
            SELECT COUNT(*) total,
                   SUM(CASE WHEN result='WIN' THEN 1 ELSE 0 END) wins,
                   SUM(CASE WHEN result='LOSS' THEN 1 ELSE 0 END) losses,
                   SUM(CASE WHEN result='DRAW' THEN 1 ELSE 0 END) draws,
                   SUM(profit_loss) profit_loss,
                   MIN(entry_time) first_entry,
                   MAX(entry_time) last_entry
            FROM trades
            """
        ).fetchone()
        strategies = [r[0] for r in db.execute("SELECT DISTINCT strategy_name FROM trades WHERE strategy_name IS NOT NULL")]
        return {
            "total": int(row["total"] or 0),
            "wins": int(row["wins"] or 0),
            "losses": int(row["losses"] or 0),
            "draws": int(row["draws"] or 0),
            "profit_loss": float(row["profit_loss"] or 0),
            "first_entry": row["first_entry"],
            "last_entry": row["last_entry"],
            "strategies": strategies,
        }
    finally:
        db.close()


def source_columns(db: sqlite3.Connection) -> list[str]:
    return [r[1] for r in db.execute("PRAGMA table_info(trades)").fetchall()]


def insert_dataset(target: sqlite3.Connection, archive: Path, info: dict) -> int:
    target.execute(
        """
        INSERT INTO external_datasets(name, source_description, detected_format, original_path, trust_level, notes)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            archive.name,
            "External demo-bot archive",
            "zip_sqlite",
            str(archive),
            "external_unverified",
            json.dumps(info, ensure_ascii=False),
        ),
    )
    return int(target.execute("SELECT last_insert_rowid()").fetchone()[0])


def import_rows(source_db: Path, target: sqlite3.Connection, dataset_id: int) -> int:
    source = connect_readonly(source_db)
    try:
        source.row_factory = sqlite3.Row
        cols = [c for c in source_columns(source) if c in set(TRADE_MAP + RAW_KEEP)]
        rows = source.execute(f"SELECT {', '.join(cols)} FROM trades ORDER BY id").fetchall()
    finally:
        source.close()

    count = 0
    for row in rows:
        raw = {c: row[c] for c in cols}
        mapped = {c: raw.get(c) for c in TRADE_MAP}
        target.execute(
            """
            INSERT INTO external_trades(
                dataset_id, asset, direction, signal_time, entry_time, expiry_time,
                duration_seconds, confidence, amount, result, profit_loss,
                entry_price, exit_price, payout, strategy_name, decision_reason,
                raw_row_json, data_quality
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                dataset_id,
                mapped.get("asset"), mapped.get("direction"), mapped.get("signal_time"),
                mapped.get("entry_time"), mapped.get("expiry_time"), mapped.get("duration_seconds"),
                mapped.get("confidence"), mapped.get("amount"), mapped.get("result"),
                mapped.get("profit_loss"), mapped.get("entry_price"), mapped.get("exit_price"),
                mapped.get("payout"), mapped.get("strategy_name"), mapped.get("decision_reason"),
                json.dumps(raw, ensure_ascii=False, default=str),
                "external_sqlite_imported",
            ),
        )
        count += 1
    return count


def import_strategy(zf: zipfile.ZipFile, target: sqlite3.Connection, dataset_id: int, name: str) -> bool:
    candidates = [n for n in zf.namelist() if n.lower().endswith("trading/strategy.py")]
    if not candidates:
        return False
    text = zf.read(candidates[0]).decode("utf-8", "replace")
    target.execute(
        """
        INSERT INTO external_strategies(dataset_id, name, description, source_file, raw_text, notes)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            dataset_id,
            name,
            "External strategy file for research only",
            candidates[0],
            text[:120000],
            "Imported into external research tables only.",
        ),
    )
    return True


def already_imported(target: sqlite3.Connection, archive: Path) -> bool:
    row = target.execute("SELECT COUNT(*) FROM external_datasets WHERE original_path=?", (str(archive),)).fetchone()
    return int(row[0] or 0) > 0


def main() -> int:
    args = parse_args()
    archive = resolve_archive(args.archive)
    print("=" * 72)
    print("QTB external trades importer")
    print("=" * 72)
    print(f"Archive: {archive}")
    print("Only trade rows and strategy text are imported. Native trades are not touched.")

    try:
        with zipfile.ZipFile(archive) as zf:
            db_name = find_db(zf)
            if not db_name:
                print("No database file found in archive.")
                return 1
            source_db = prepare_source_db(zf, db_name)
            info = summary(source_db)
            print(f"Detected database: {db_name}")
            print(f"Detected trades: {info['total']}")
            print(f"Wins/Losses/Draws: {info.get('wins', 0)}/{info.get('losses', 0)}/{info.get('draws', 0)}")
            print(f"Profit/Loss: {info.get('profit_loss', 0):.2f}")
            print(f"Period: {info.get('first_entry')} -> {info.get('last_entry')}")
            print(f"Strategies: {', '.join(info.get('strategies') or []) or 'none'}")

            if not args.yes:
                print("Dry run only. Run again with --yes to import.")
                return 0

            with sqlite3.connect(DB_PATH) as target:
                init_tables(target)
                if already_imported(target, archive) and not args.force:
                    print("This archive path was already imported. Use --force to import again.")
                    return 0
                dataset_id = insert_dataset(target, archive, info)
                imported = import_rows(source_db, target, dataset_id)
                strategy_name = (info.get("strategies") or ["external_strategy"])[0]
                strategy_done = import_strategy(zf, target, dataset_id, strategy_name)
                target.execute(
                    "INSERT INTO external_import_logs(dataset_id, level, message) VALUES (?, ?, ?)",
                    (dataset_id, "INFO", f"Imported {imported} external trades from {archive.name}"),
                )
                target.commit()
    finally:
        cleanup_source_db()

    print(f"Imported dataset id: {dataset_id}")
    print(f"Imported external trades: {imported}")
    print(f"Imported strategy: {strategy_done}")
    print("External records are separate from native trades.")
    print("Temporary external source database was cleaned up.")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
