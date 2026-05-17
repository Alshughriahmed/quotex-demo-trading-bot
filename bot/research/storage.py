from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Sequence

from market_sources import MarketCandle, validate_candle_sequence


def store_market_candles(db_path: str | Path, candles: Sequence[MarketCandle]) -> int:
    """Validate and store read-only market candles in research tables.

    This function stores market data only. It never writes native trades and
    never performs or requests order execution.
    """

    issues = validate_candle_sequence(candles)
    if issues:
        raise ValueError("Invalid market candle sequence: " + "; ".join(issues[:10]))

    path = Path(db_path)
    inserted_or_updated = 0

    with sqlite3.connect(path) as db:
        db.execute("PRAGMA foreign_keys = ON")
        for candle in candles:
            db.execute(
                """
                INSERT INTO research_market_candles (
                    source_key,
                    asset,
                    timeframe_seconds,
                    candle_time,
                    open,
                    high,
                    low,
                    close,
                    volume,
                    is_closed,
                    raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_key, asset, timeframe_seconds, candle_time)
                DO UPDATE SET
                    open=excluded.open,
                    high=excluded.high,
                    low=excluded.low,
                    close=excluded.close,
                    volume=excluded.volume,
                    is_closed=excluded.is_closed,
                    raw_json=excluded.raw_json
                """,
                (
                    candle.source_key,
                    candle.asset,
                    candle.timeframe_seconds,
                    candle.candle_time.isoformat(),
                    candle.open,
                    candle.high,
                    candle.low,
                    candle.close,
                    candle.volume,
                    1 if candle.is_closed else 0,
                    json.dumps(
                        {
                            "source_key": candle.source_key,
                            "asset": candle.asset,
                            "timeframe_seconds": candle.timeframe_seconds,
                            "candle_time": candle.candle_time.isoformat(),
                            "open": candle.open,
                            "high": candle.high,
                            "low": candle.low,
                            "close": candle.close,
                            "volume": candle.volume,
                            "is_closed": candle.is_closed,
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                ),
            )
            inserted_or_updated += 1
        db.commit()

    return inserted_or_updated
