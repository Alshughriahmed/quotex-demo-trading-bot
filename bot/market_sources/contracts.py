from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, Sequence, runtime_checkable


@dataclass(frozen=True, slots=True)
class MarketCandle:
    """A closed or forming market candle from a read-only market source.

    This object contains market data only. It must never contain account,
    session, token, order, or execution details.
    """

    source_key: str
    asset: str
    timeframe_seconds: int
    candle_time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float | None = None
    is_closed: bool = True


@dataclass(frozen=True, slots=True)
class MarketSourceInfo:
    source_key: str
    label: str
    configured: bool
    enabled: bool
    safe_for_signal_only: bool
    reason: str


@runtime_checkable
class ReadOnlyMarketSource(Protocol):
    """Protocol for signal-only market data adapters.

    Implementations may read prices/candles, but must not place orders,
    select account type, submit buys, or expose secrets.
    """

    @property
    def source_key(self) -> str:
        ...

    @property
    def label(self) -> str:
        ...

    def status(self) -> MarketSourceInfo:
        ...

    def fetch_recent_candles(
        self,
        asset: str,
        timeframe_seconds: int,
        limit: int,
    ) -> Sequence[MarketCandle]:
        ...


def validate_candle(candle: MarketCandle) -> list[str]:
    issues: list[str] = []

    if not candle.source_key.strip():
        issues.append("source_key is required")
    if not candle.asset.strip():
        issues.append("asset is required")
    if candle.timeframe_seconds <= 0:
        issues.append("timeframe_seconds must be positive")
    if candle.open <= 0 or candle.high <= 0 or candle.low <= 0 or candle.close <= 0:
        issues.append("OHLC prices must be positive")
    if candle.high < max(candle.open, candle.close, candle.low):
        issues.append("high must be greater than or equal to open/low/close")
    if candle.low > min(candle.open, candle.close, candle.high):
        issues.append("low must be less than or equal to open/high/close")
    if candle.volume is not None and candle.volume < 0:
        issues.append("volume cannot be negative")

    return issues


def validate_candle_sequence(candles: Sequence[MarketCandle]) -> list[str]:
    issues: list[str] = []
    if not candles:
        return ["at least one candle is required"]

    first = candles[0]
    previous_time = first.candle_time

    for index, candle in enumerate(candles):
        for issue in validate_candle(candle):
            issues.append(f"candle[{index}]: {issue}")
        if candle.source_key != first.source_key:
            issues.append(f"candle[{index}]: source_key differs from first candle")
        if candle.asset != first.asset:
            issues.append(f"candle[{index}]: asset differs from first candle")
        if candle.timeframe_seconds != first.timeframe_seconds:
            issues.append(f"candle[{index}]: timeframe_seconds differs from first candle")
        if index > 0 and candle.candle_time <= previous_time:
            issues.append(f"candle[{index}]: candle_time must be strictly increasing")
        previous_time = candle.candle_time

    return issues
