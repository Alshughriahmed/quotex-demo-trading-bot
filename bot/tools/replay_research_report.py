from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


BOT_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BOT_DIR / "data.db"


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def table_exists(db: sqlite3.Connection, table_name: str) -> bool:
    row = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone()
    return row is not None


def scalar(db: sqlite3.Connection, query: str, params: tuple[Any, ...] = ()) -> Any:
    row = db.execute(query, params).fetchone()
    if not row:
        return None
    return row[0]


def print_section(title: str) -> None:
    print("-" * 72)
    print(title)
    print("-" * 72)


def print_rows(title: str, rows: list[sqlite3.Row], columns: list[str]) -> None:
    print_section(title)
    if not rows:
        print("No data.")
        return
    print(" | ".join(columns))
    print(" | ".join("-" * len(column) for column in columns))
    for row in rows:
        values = []
        for column in columns:
            value = row[column]
            if isinstance(value, float):
                values.append(f"{value:.2f}")
            else:
                values.append(str(value if value is not None else ""))
        print(" | ".join(values))


def safe_rate(wins: int, total: int) -> float:
    return round((wins / total) * 100, 2) if total else 0.0


def overview(db: sqlite3.Connection) -> dict[str, Any]:
    candles = int(scalar(db, "SELECT COUNT(*) FROM research_market_candles") or 0)
    signals = int(scalar(db, "SELECT COUNT(*) FROM research_signals") or 0)
    outcomes = int(scalar(db, "SELECT COUNT(*) FROM research_signal_outcomes") or 0)
    wins = int(scalar(db, "SELECT COUNT(*) FROM research_signal_outcomes WHERE result = 'WIN'") or 0)
    losses = int(scalar(db, "SELECT COUNT(*) FROM research_signal_outcomes WHERE result = 'LOSS'") or 0)
    draws = int(scalar(db, "SELECT COUNT(*) FROM research_signal_outcomes WHERE result = 'DRAW'") or 0)
    unknown = int(scalar(db, "SELECT COUNT(*) FROM research_signal_outcomes WHERE result = 'UNKNOWN'") or 0)
    profit_loss = float(scalar(db, "SELECT COALESCE(SUM(theoretical_profit_loss), 0) FROM research_signal_outcomes") or 0)
    return {
        "candles": candles,
        "signals": signals,
        "outcomes": outcomes,
        "wins": wins,
        "losses": losses,
        "draws": draws,
        "unknown": unknown,
        "win_rate": safe_rate(wins, wins + losses + draws),
        "profit_loss": round(profit_loss, 2),
    }


def print_overview(db: sqlite3.Connection) -> dict[str, Any]:
    data = overview(db)
    print_section("Replay research overview")
    print(f"Research candles: {data['candles']}")
    print(f"Research signals: {data['signals']}")
    print(f"Research outcomes: {data['outcomes']}")
    print(f"WIN/LOSS/DRAW/UNKNOWN: {data['wins']}/{data['losses']}/{data['draws']}/{data['unknown']}")
    print(f"Win rate: {data['win_rate']:.2f}%")
    print(f"Theoretical profit/loss: {data['profit_loss']:.2f}")
    return data


def performance_by_asset(db: sqlite3.Connection) -> None:
    rows = db.execute(
        """
        SELECT s.asset,
               COUNT(*) AS outcomes,
               SUM(CASE WHEN o.result = 'WIN' THEN 1 ELSE 0 END) AS wins,
               SUM(CASE WHEN o.result = 'LOSS' THEN 1 ELSE 0 END) AS losses,
               SUM(CASE WHEN o.result = 'DRAW' THEN 1 ELSE 0 END) AS draws,
               ROUND(100.0 * SUM(CASE WHEN o.result = 'WIN' THEN 1 ELSE 0 END) /
                    NULLIF(SUM(CASE WHEN o.result IN ('WIN','LOSS','DRAW') THEN 1 ELSE 0 END), 0), 2) AS win_rate,
               ROUND(SUM(COALESCE(o.theoretical_profit_loss, 0)), 2) AS profit_loss
        FROM research_signal_outcomes o
        INNER JOIN research_signals s ON s.id = o.signal_id
        GROUP BY s.asset
        ORDER BY profit_loss DESC, outcomes DESC
        LIMIT 20
        """
    ).fetchall()
    print_rows("Performance by asset", rows, ["asset", "outcomes", "wins", "losses", "draws", "win_rate", "profit_loss"])


def performance_by_direction(db: sqlite3.Connection) -> None:
    rows = db.execute(
        """
        SELECT s.direction,
               COUNT(*) AS outcomes,
               SUM(CASE WHEN o.result = 'WIN' THEN 1 ELSE 0 END) AS wins,
               SUM(CASE WHEN o.result = 'LOSS' THEN 1 ELSE 0 END) AS losses,
               SUM(CASE WHEN o.result = 'DRAW' THEN 1 ELSE 0 END) AS draws,
               ROUND(100.0 * SUM(CASE WHEN o.result = 'WIN' THEN 1 ELSE 0 END) /
                    NULLIF(SUM(CASE WHEN o.result IN ('WIN','LOSS','DRAW') THEN 1 ELSE 0 END), 0), 2) AS win_rate,
               ROUND(SUM(COALESCE(o.theoretical_profit_loss, 0)), 2) AS profit_loss
        FROM research_signal_outcomes o
        INNER JOIN research_signals s ON s.id = o.signal_id
        GROUP BY s.direction
        ORDER BY profit_loss DESC, outcomes DESC
        """
    ).fetchall()
    print_rows("Performance by direction", rows, ["direction", "outcomes", "wins", "losses", "draws", "win_rate", "profit_loss"])


def performance_by_confidence(db: sqlite3.Connection) -> None:
    rows = db.execute(
        """
        SELECT CASE
                   WHEN s.confidence < 70 THEN '<70'
                   WHEN s.confidence < 80 THEN '70-79'
                   WHEN s.confidence < 90 THEN '80-89'
                   WHEN s.confidence < 95 THEN '90-94'
                   ELSE '95-100'
               END AS confidence_bucket,
               COUNT(*) AS outcomes,
               SUM(CASE WHEN o.result = 'WIN' THEN 1 ELSE 0 END) AS wins,
               SUM(CASE WHEN o.result = 'LOSS' THEN 1 ELSE 0 END) AS losses,
               SUM(CASE WHEN o.result = 'DRAW' THEN 1 ELSE 0 END) AS draws,
               ROUND(100.0 * SUM(CASE WHEN o.result = 'WIN' THEN 1 ELSE 0 END) /
                    NULLIF(SUM(CASE WHEN o.result IN ('WIN','LOSS','DRAW') THEN 1 ELSE 0 END), 0), 2) AS win_rate,
               ROUND(SUM(COALESCE(o.theoretical_profit_loss, 0)), 2) AS profit_loss
        FROM research_signal_outcomes o
        INNER JOIN research_signals s ON s.id = o.signal_id
        GROUP BY confidence_bucket
        ORDER BY confidence_bucket
        """
    ).fetchall()
    print_rows("Performance by confidence bucket", rows, ["confidence_bucket", "outcomes", "wins", "losses", "draws", "win_rate", "profit_loss"])


def performance_by_hour(db: sqlite3.Connection) -> None:
    rows = db.execute(
        """
        SELECT strftime('%H', s.signal_time) AS utc_hour,
               COUNT(*) AS outcomes,
               SUM(CASE WHEN o.result = 'WIN' THEN 1 ELSE 0 END) AS wins,
               SUM(CASE WHEN o.result = 'LOSS' THEN 1 ELSE 0 END) AS losses,
               SUM(CASE WHEN o.result = 'DRAW' THEN 1 ELSE 0 END) AS draws,
               ROUND(100.0 * SUM(CASE WHEN o.result = 'WIN' THEN 1 ELSE 0 END) /
                    NULLIF(SUM(CASE WHEN o.result IN ('WIN','LOSS','DRAW') THEN 1 ELSE 0 END), 0), 2) AS win_rate,
               ROUND(SUM(COALESCE(o.theoretical_profit_loss, 0)), 2) AS profit_loss
        FROM research_signal_outcomes o
        INNER JOIN research_signals s ON s.id = o.signal_id
        GROUP BY utc_hour
        ORDER BY profit_loss DESC, outcomes DESC
        LIMIT 24
        """
    ).fetchall()
    print_rows("Performance by UTC hour", rows, ["utc_hour", "outcomes", "wins", "losses", "draws", "win_rate", "profit_loss"])


def pending_outcomes(db: sqlite3.Connection) -> None:
    print_section("Pending outcome status")
    pending = int(
        scalar(
            db,
            """
            SELECT COUNT(*)
            FROM research_signals s
            LEFT JOIN research_signal_outcomes o ON o.signal_id = s.id
            WHERE o.id IS NULL
              AND s.direction IN ('CALL','PUT')
            """,
        )
        or 0
    )
    no_trade = int(scalar(db, "SELECT COUNT(*) FROM research_signals WHERE direction = 'NO_TRADE'") or 0)
    print(f"Trade signals without outcome: {pending}")
    print(f"NO_TRADE research rows: {no_trade}")


def save_analysis_run(db: sqlite3.Connection, summary: dict[str, Any]) -> None:
    db.execute(
        """
        INSERT INTO research_analysis_runs (name, input_scope, result_summary_json, notes)
        VALUES (?, ?, ?, ?)
        """,
        (
            "replay_research_report",
            "research_signal_outcomes joined with research_signals",
            json.dumps(summary, ensure_ascii=False, sort_keys=True),
            "Read-only report. No native trades changed.",
        ),
    )
    db.commit()


def main() -> int:
    print("=" * 72)
    print("QTB replay research performance report")
    print("=" * 72)
    print("This reads research_* tables only. It does not start the bot or trade.")
    print(f"Database: {DB_PATH}")

    if not DB_PATH.exists():
        print("Database not found. Run init_signal_research_tables first.")
        return 1

    with connect() as db:
        needed = ["research_market_candles", "research_signals", "research_signal_outcomes", "research_analysis_runs"]
        missing = [table for table in needed if not table_exists(db, table)]
        if missing:
            print(f"Missing research tables: {', '.join(missing)}")
            return 1

        summary = print_overview(db)
        pending_outcomes(db)
        if summary["outcomes"] == 0:
            print_section("Report decision")
            print("No evaluated replay outcomes yet.")
            print("Import candles, run replay signals, then evaluate outcomes before using this report.")
            return 0

        performance_by_asset(db)
        performance_by_direction(db)
        performance_by_confidence(db)
        performance_by_hour(db)
        save_analysis_run(db, summary)

    print("=" * 72)
    print("Replay research report finished. No native trades were changed.")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
