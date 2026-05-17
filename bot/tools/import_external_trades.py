from __future__ import annotations

import argparse
import json
import shutil
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
    parser.add_argument("archive", nargs="?", help="Zip file/folder name or path. Defaults to newest zip or extracted folder in bot/external_inputs.")
    parser.add_argument("--yes", action="store_true", help="Actually import. Without this flag, only dry-run summary is printed.")
    parser.add_argument("--force", action="store_true", help="Allow importing the same archive path again.")
    return parser.parse_args()


def has_external_database(path: Path) -> bool:
    if path.is_file() and path.suffix.lower() == ".zip":
        return True
    if path.is_dir():
        return any(candidate.name.lower().endswith(".db") for candidate in path.rglob("*.db"))
    return False


def resolve_archive(raw: str | None) -> Path:
    if raw:
        path = Path(raw).expanduser()
        if not path.is_absolute():
            path = INBOX_DIR / path
    else:
        candidates = [path for path in INBOX_DIR.iterdir() if has_external_database(path)] if INBOX_DIR.exists() else []
        candidates = sorted(candidates, key=lambda p: p.stat().st_mtime, reverse=True)
        if not candidates:
            raise FileNotFoundError(f"No external zip file or extracted project folder found in {INBOX_DIR}")
        path = candidates[0]
    path = path.resolve()
    if not has_external_database(path):
        raise ValueError("Only .zip files or extracted project folders containing a .db file are supported.")
    return path


def cleanup_source_db() -> None:
    try:
        SOURCE_DB_PATH.unlink(missing_ok=True)
    except OSError:
        pass


def copy_source_db(source: Path) -> Path:
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    cleanup_source_db()
    shutil.copy2(source, SOURCE_DB_PATH)
    return SOURCE_DB_PATH


def prepare_source_db_from_zip(zf: zipfile.ZipFile, db_name: str) -> Path:
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    cleanup_source_db()
    SOURCE_DB_PATH.write_bytes(zf.read(db_name))
    return SOURCE_DB_PATH


def find_db_in_zip(zf: zipfile.ZipFile) -> str | None:
    names = [n for n in zf.namelist() if n.lower().endswith(".db")]
    preferred = [name for name in names if name.lower().endswith("data.db") and "backup" not in name.lower()]
    if "bot/data.db" in names:
        return "bot/data.db"
    if "data.db" in names:
        return "data.db"
    return preferred[0] if preferred else (names[0] if names else None)


def find_db_in_folder(folder: Path) -> Path | None:
    candidates = [path for path in folder.rglob("*.db") if path.is_file()]
    non_backup = [path for path in candidates if "backup" not in str(path).lower()]
    preferred = [path for path in non_backup if path.name.lower() == "data.db"]
    if preferred:
        return sorted(preferred, key=lambda p: len(p.parts))[0]
    return sorted(non_backup or candidates, key=lambda p: (len(p.parts), str(p)))[0] if candidates else None


def read_strategy_from_zip(zf: zipfile.ZipFile) -> tuple[str, str] | None:
    candidates = [n for n in zf.namelist() if n.lower().endswith("trading/strategy.py")]
    if not candidates:
        return None
    name = candidates[0]
    return name, zf.read(name).decode("utf-8", "replace")


def read_strategy_from_folder(folder: Path) -> tuple[str, str] | None:
    candidates = sorted(folder.rglob("strategy.py"), key=lambda p: (len(p.parts), str(p)))
    candidates = [path for path in candidates if "trading" in [part.lower() for part in path.parts]] or candidates
    if not candidates:
        return None
    path = candidates[0]
    return str(path.relative_to(folder)), path.read_text(encoding="utf-8", errors="replace")


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


def insert_dataset(target: sqlite3.Connection, archive: Path, info: dict, detected_format: str) -> int:
    target.execute(
        """
        INSERT INTO external_datasets(name, source_description, detected_format, original_path, trust_level, notes)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            archive.name,
            "External demo-bot archive or extracted folder",
            detected_format,
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


def import_strategy_text(target: sqlite3.Connection, dataset_id: int, name: str, strategy: tuple[str, str] | None) -> bool:
    if not strategy:
        return False
    source_file, text = strategy
    target.execute(
        """
        INSERT INTO external_strategies(dataset_id, name, description, source_file, raw_text, notes)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            dataset_id,
            name,
            "External strategy file for research only",
            source_file,
            text[:120000],
            "Imported into external research tables only.",
        ),
    )
    return True


def already_imported(target: sqlite3.Connection, archive: Path) -> bool:
    row = target.execute("SELECT COUNT(*) FROM external_datasets WHERE original_path=?", (str(archive),)).fetchone()
    return int(row[0] or 0) > 0


def load_source(path: Path) -> tuple[Path, dict, str, tuple[str, str] | None, str]:
    if path.is_file():
        with zipfile.ZipFile(path) as zf:
            db_name = find_db_in_zip(zf)
            if not db_name:
                raise FileNotFoundError("No database file found in archive.")
            source_db = prepare_source_db_from_zip(zf, db_name)
            info = summary(source_db)
            strategy = read_strategy_from_zip(zf)
            return source_db, info, "zip_sqlite", strategy, db_name

    db_file = find_db_in_folder(path)
    if not db_file:
        raise FileNotFoundError("No database file found in extracted project folder.")
    source_db = copy_source_db(db_file)
    info = summary(source_db)
    strategy = read_strategy_from_folder(path)
    return source_db, info, "folder_sqlite", strategy, str(db_file.relative_to(path))


def main() -> int:
    args = parse_args()
    archive = resolve_archive(args.archive)
    print("=" * 72)
    print("QTB external trades importer")
    print("=" * 72)
    print(f"Source: {archive}")
    print("Only trade rows and strategy text are imported. Native trades are not touched.")

    dataset_id = 0
    imported = 0
    strategy_done = False
    try:
        source_db, info, detected_format, strategy, db_label = load_source(archive)
        print(f"Detected format: {detected_format}")
        print(f"Detected database: {db_label}")
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
                print("This source path was already imported. Use --force to import again.")
                return 0
            dataset_id = insert_dataset(target, archive, info, detected_format)
            imported = import_rows(source_db, target, dataset_id)
            strategy_name = (info.get("strategies") or ["external_strategy"])[0]
            strategy_done = import_strategy_text(target, dataset_id, strategy_name, strategy)
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