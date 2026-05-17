from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


BOT_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BOT_DIR / "data.db"
if str(BOT_DIR) not in sys.path:
    sys.path.insert(0, str(BOT_DIR))

from trading.strategy import STRATEGY_PROFILES, analyze

STRATEGY_NAME = "ema_rsi_candle_v1"
STRATEGY_VERSION = "replay_signal_only_v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run signal-only strategy decisions over replay candles.")
    parser.add_argument("--source-key", default="", help="Optional source_key filter.")
    parser.add_argument("--asset", default="", help="Optional asset filter.")
    parser.add_argument("--timeframe", type=int, default=60, help="Candle timeframe in seconds.")
    parser.add_argument("--duration", type=int, default=60, help="Signal duration in seconds / strategy profile key.")
    parser.add_argument("--limit", type=int, default=0, help="Optional max signals to generate per group, 0 means all.")
    parser.add_argument("--include-no-trade", action="store_true", help="Store NO_TRADE decisions too.")
    parser.add_argument("--yes", action="store_true", help="Actually insert into research_signals. Without this flag, dry-run only.")
    return parser.parse_args()


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


def load_groups(db: sqlite3.Connection, source_key: str, asset: str, timeframe: int) -> dict[tuple[str, str, int], list[sqlite3.Row]]:
    where = ["timeframe_seconds = ?"]
    params: list[Any] = [timeframe]
    if source_key:
        where.append("source_key = ?")
        params.append(source_key)
    if asset:
        where.append("asset = ?")
        params.append(asset)

    rows = db.execute(
        f"""
        SELECT *
        FROM research_market_candles
        WHERE {' AND '.join(where)}
        ORDER BY source_key, asset, timeframe_seconds, candle_time
        """,
        tuple(params),
    ).fetchall()

    groups: dict[tuple[str, str, int], list[sqlite3.Row]] = {}
    for row in rows:
        key = (str(row["source_key"]), str(row["asset"]), int(row["timeframe_seconds"]))
        groups.setdefault(key, []).append(row)
    return groups


def row_to_strategy_candle(row: sqlite3.Row) -> dict[str, Any]:
    candle_time = datetime.fromisoformat(str(row["candle_time"]).replace("Z", "+00:00"))
    if candle_time.tzinfo is None:
        candle_time = candle_time.replace(tzinfo=timezone.utc)
    return {
        "time": candle_time.timestamp(),
        "open": float(row["open"]),
        "high": float(row["high"]),
        "low": float(row["low"]),
        "close": float(row["close"]),
    }


def candle_time_datetime(row: sqlite3.Row) -> datetime:
    candle_time = datetime.fromisoformat(str(row["candle_time"]).replace("Z", "+00:00"))
    if candle_time.tzinfo is None:
        candle_time = candle_time.replace(tzinfo=timezone.utc)
    return candle_time.astimezone(timezone.utc)


def candle_time_iso(row: sqlite3.Row) -> str:
    return candle_time_datetime(row).isoformat()


def expiry_time_iso(row: sqlite3.Row, duration: int) -> str:
    return (candle_time_datetime(row) + timedelta(seconds=duration)).isoformat()


def required_candles(duration: int) -> int:
    profile = STRATEGY_PROFILES.get(duration)
    if profile:
        return int(profile["min_candles"])
    closest = min(STRATEGY_PROFILES, key=lambda key: abs(key - duration))
    return int(STRATEGY_PROFILES[closest]["min_candles"])


def create_run(db: sqlite3.Connection, source_key: str, timeframe: int, duration: int, dry_run: bool) -> int | None:
    if dry_run:
        return None
    cursor = db.execute(
        """
        INSERT INTO research_strategy_runs (
            strategy_name,
            strategy_version,
            source_key,
            timeframe_seconds,
            settings_json,
            notes,
            status
        ) VALUES (?, ?, ?, ?, ?, ?, 'OPEN')
        """,
        (
            STRATEGY_NAME,
            STRATEGY_VERSION,
            source_key or "mixed",
            timeframe,
            json.dumps({"duration_seconds": duration}, sort_keys=True),
            "Replay signal-only run. No native trades or order execution.",
        ),
    )
    return int(cursor.lastrowid)


def finish_run(db: sqlite3.Connection, run_id: int | None, status: str, notes: str = "") -> None:
    if run_id is None:
        return
    db.execute(
        "UPDATE research_strategy_runs SET finished_at = ?, status = ?, notes = COALESCE(notes, '') || ? WHERE id = ?",
        (datetime.now(timezone.utc).isoformat(), status, f"\n{notes}" if notes else "", run_id),
    )


def insert_signal(
    db: sqlite3.Connection,
    run_id: int | None,
    row: sqlite3.Row,
    decision: Any,
    duration: int,
) -> None:
    signal_time = candle_time_iso(row)
    expiry_time = expiry_time_iso(row, duration)
    indicators = dict(decision.indicators or {})
    db.execute(
        """
        INSERT INTO research_signals (
            run_id,
            source_key,
            strategy_name,
            strategy_version,
            asset,
            direction,
            signal_time,
            entry_time,
            expiry_time,
            duration_seconds,
            confidence,
            rsi,
            ema_fast,
            ema_slow,
            ema_gap,
            adx,
            atr,
            volatility,
            candle_body_ratio,
            reason,
            indicators_json,
            candles_ref_json,
            data_quality
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'replay')
        """,
        (
            run_id,
            row["source_key"],
            STRATEGY_NAME,
            STRATEGY_VERSION,
            row["asset"],
            decision.direction,
            signal_time,
            signal_time,
            expiry_time,
            duration,
            float(decision.confidence or 0),
            decision.rsi,
            decision.ema_fast,
            decision.ema_slow,
            indicators.get("ema_gap"),
            indicators.get("adx"),
            indicators.get("atr"),
            decision.volatility,
            indicators.get("last_body_ratio"),
            decision.reason,
            json.dumps(indicators, ensure_ascii=False, sort_keys=True),
            json.dumps({"last_candle_time": signal_time, "expiry_time": expiry_time}, ensure_ascii=False, sort_keys=True),
        ),
    )


def summarize_decisions(decisions: list[tuple[sqlite3.Row, Any]]) -> dict[str, int]:
    summary = {"CALL": 0, "PUT": 0, "NO_TRADE": 0}
    for _, decision in decisions:
        summary[decision.direction] = summary.get(decision.direction, 0) + 1
    return summary


def run_group(rows: list[sqlite3.Row], duration: int, limit: int, include_no_trade: bool) -> list[tuple[sqlite3.Row, Any]]:
    required = required_candles(duration)
    decisions: list[tuple[sqlite3.Row, Any]] = []
    for index in range(required, len(rows) + 1):
        window_rows = rows[:index]
        strategy_candles = [row_to_strategy_candle(row) for row in window_rows]
        decision = analyze(
            asset=str(rows[index - 1]["asset"]),
            candles=strategy_candles,
            duration_seconds=duration,
            drop_open_candle=False,
        )
        if include_no_trade or decision.has_trade:
            decisions.append((rows[index - 1], decision))
        if limit and len(decisions) >= limit:
            break
    return decisions


def main() -> int:
    args = parse_args()
    print("=" * 72)
    print("QTB replay signal-only strategy runner")
    print("=" * 72)
    print("This reads research_market_candles and writes research_signals only when confirmed.")
    print("It does not start the bot, does not connect to a broker, and does not trade.")
    print(f"Database: {DB_PATH}")

    if not DB_PATH.exists():
        print("Database not found. Run init_signal_research_tables first.")
        return 1

    required = required_candles(args.duration)
    print(f"Strategy: {STRATEGY_NAME} / {STRATEGY_VERSION}")
    print(f"Timeframe: {args.timeframe}s")
    print(f"Duration/profile: {args.duration}s")
    print(f"Minimum candles needed: {required}")
    print(f"Include NO_TRADE decisions: {args.include_no_trade}")

    with connect() as db:
        if not table_exists(db, "research_market_candles") or not table_exists(db, "research_signals"):
            print("Research tables are missing. Run init_signal_research_tables first.")
            return 1

        groups = load_groups(db, args.source_key.strip(), args.asset.strip(), args.timeframe)
        if not groups:
            print("No replay candles matched the requested filters.")
            return 0

        all_decisions: list[tuple[tuple[str, str, int], list[tuple[sqlite3.Row, Any]]]] = []
        for key, rows in groups.items():
            decisions = run_group(rows, args.duration, max(0, args.limit), args.include_no_trade)
            all_decisions.append((key, decisions))

        total_candidates = sum(len(decisions) for _, decisions in all_decisions)
        print(f"Groups found: {len(groups)}")
        print(f"Signal rows to {'insert' if args.yes else 'preview'}: {total_candidates}")

        for key, decisions in all_decisions:
            source_key, asset, timeframe = key
            summary = summarize_decisions(decisions)
            print(f"- {source_key} / {asset} / {timeframe}s: {len(decisions)} rows, CALL={summary.get('CALL', 0)}, PUT={summary.get('PUT', 0)}, NO_TRADE={summary.get('NO_TRADE', 0)}")

        if not args.yes:
            print("Dry run only. Re-run with --yes to insert research_signals.")
            return 0

        run_id = create_run(db, args.source_key.strip(), args.timeframe, args.duration, dry_run=False)
        inserted = 0
        try:
            for _, decisions in all_decisions:
                for row, decision in decisions:
                    insert_signal(db, run_id, row, decision, args.duration)
                    inserted += 1
            finish_run(db, run_id, "FINISHED", f"Inserted research signals: {inserted}")
            db.commit()
        except Exception:
            finish_run(db, run_id, "ERROR", "Replay signal run failed before completion.")
            db.commit()
            raise

        print(f"Inserted research signals: {inserted}")
        print("Signals are research-only and separate from native trades.")

    print("=" * 72)
    print("Replay signal runner finished. No native trades were changed.")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())