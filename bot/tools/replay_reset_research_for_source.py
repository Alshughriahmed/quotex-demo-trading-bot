from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

BOT_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BOT_DIR / "data.db"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reset stored replay research signals/outcomes for one source and strategy version.")
    parser.add_argument("--source-key", required=True, help="Replay source_key to reset.")
    parser.add_argument("--strategy-version", required=True, help="Strategy version to reset.")
    parser.add_argument("--asset", default="", help="Optional asset filter, for example USD/CAD.")
    parser.add_argument("--yes", action="store_true", help="Actually delete matching research signals/outcomes. Without this flag, dry-run only.")
    return parser.parse_args()


def connect() -> sqlite3.Connection:
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    return db


def table_exists(db: sqlite3.Connection, name: str) -> bool:
    return db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None


def where_clause(source_key: str, strategy_version: str, asset: str) -> tuple[str, list[object]]:
    clauses = ["source_key = ?", "strategy_version = ?"]
    params: list[object] = [source_key, strategy_version]
    if asset:
        clauses.append("asset = ?")
        params.append(asset)
    return " AND ".join(clauses), params


def main() -> int:
    args = parse_args()
    source_key = args.source_key.strip()
    strategy_version = args.strategy_version.strip()
    asset = args.asset.strip()

    print("=" * 72)
    print("QTB replay research reset for one source")
    print("=" * 72)
    print("This deletes stored research_signals and research_signal_outcomes only for the requested source/strategy.")
    print("It does not delete candles, does not touch native trades, does not start the bot, and does not trade.")
    print(f"Database: {DB_PATH}")
    print(f"Source key: {source_key}")
    print(f"Strategy version: {strategy_version}")
    print(f"Asset filter: {asset or 'ALL'}")

    if not source_key or not strategy_version:
        print("Missing source_key or strategy_version. Cancelled.")
        return 1
    if not DB_PATH.exists():
        print("Database not found.")
        return 1

    with connect() as db:
        missing = [name for name in ["research_signals", "research_signal_outcomes"] if not table_exists(db, name)]
        if missing:
            print(f"Missing research tables: {', '.join(missing)}")
            return 1

        where_sql, params = where_clause(source_key, strategy_version, asset)
        signal_count = int(db.execute(f"SELECT COUNT(*) FROM research_signals WHERE {where_sql}", tuple(params)).fetchone()[0] or 0)
        outcome_count = int(
            db.execute(
                f"""
                SELECT COUNT(*)
                FROM research_signal_outcomes
                WHERE signal_id IN (SELECT id FROM research_signals WHERE {where_sql})
                """,
                tuple(params),
            ).fetchone()[0]
            or 0
        )
        print(f"Matching research signals: {signal_count}")
        print(f"Matching research outcomes: {outcome_count}")

        if not args.yes:
            print("Dry run only. Re-run with --yes to delete matching research rows.")
            print("=" * 72)
            return 0

        db.execute(
            f"DELETE FROM research_signal_outcomes WHERE signal_id IN (SELECT id FROM research_signals WHERE {where_sql})",
            tuple(params),
        )
        db.execute(f"DELETE FROM research_signals WHERE {where_sql}", tuple(params))
        if table_exists(db, "research_strategy_runs") and not asset:
            db.execute(
                "DELETE FROM research_strategy_runs WHERE source_key = ? AND strategy_version = ?",
                (source_key, strategy_version),
            )
        db.commit()
        print("Deleted matching research rows.")
        print("Candles were not deleted. Native trades were not changed.")

    print("=" * 72)
    print("Replay research reset finished.")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
