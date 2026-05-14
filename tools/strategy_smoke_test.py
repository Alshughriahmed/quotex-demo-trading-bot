from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bot"))

from trading.strategy import CALL, NO_TRADE, PUT, analyze  # noqa: E402


def make_trend_candles(
    count: int,
    start: float,
    step: float,
    body: float,
    wick: float,
) -> list[dict[str, float]]:
    candles = []
    price = start
    for index in range(count):
        open_price = price
        close_price = price + step
        high = max(open_price, close_price) + wick
        low = min(open_price, close_price) - wick
        candles.append(
            {
                "time": float(index),
                "open": round(open_price, 8),
                "high": round(high, 8),
                "low": round(low, 8),
                "close": round(close_price, 8),
            }
        )
        price = close_price + body
    return candles


def make_flat_candles(count: int, price: float = 1.0) -> list[dict[str, float]]:
    candles = []
    for index in range(count):
        candles.append(
            {
                "time": float(index),
                "open": price,
                "high": price + 0.00001,
                "low": price - 0.00001,
                "close": price,
            }
        )
    return candles


def assert_direction(name: str, actual: str, expected: str) -> None:
    if actual != expected:
        raise AssertionError(f"{name}: expected {expected}, got {actual}")


def require_reason(name: str, reason: str, expected: str) -> None:
    if expected not in reason:
        raise AssertionError(f"{name}: expected reason to include {expected!r}, got {reason!r}")


def main() -> int:
    uptrend = make_trend_candles(90, start=1.0, step=0.00025, body=0.00003, wick=0.00005)
    up = analyze("TEST/UP", uptrend, duration_seconds=180, min_confidence=65, drop_open_candle=True)
    assert_direction("uptrend", up.direction, CALL)
    if up.confidence < 65:
        raise AssertionError(f"uptrend confidence too low: {up.confidence}")
    require_reason("uptrend", up.reason, "ضغط صعود")

    downtrend = make_trend_candles(90, start=1.2, step=-0.00025, body=-0.00003, wick=0.00005)
    down = analyze("TEST/DOWN", downtrend, duration_seconds=180, min_confidence=65, drop_open_candle=True)
    assert_direction("downtrend", down.direction, PUT)
    if down.confidence < 65:
        raise AssertionError(f"downtrend confidence too low: {down.confidence}")
    require_reason("downtrend", down.reason, "ضغط هبوط")
    if down.confidence < up.confidence - 8:
        raise AssertionError(
            "downtrend confidence is unexpectedly far below uptrend confidence: "
            f"down={down.confidence}, up={up.confidence}"
        )

    flat = analyze("TEST/FLAT", make_flat_candles(90), duration_seconds=180, min_confidence=65, drop_open_candle=True)
    assert_direction("flat_market", flat.direction, NO_TRADE)

    short = analyze("TEST/SHORT", make_flat_candles(10), duration_seconds=180, min_confidence=65, drop_open_candle=True)
    assert_direction("too_few_candles", short.direction, NO_TRADE)

    print("Strategy smoke test passed.")
    print(f"uptrend: {up.direction} confidence={up.confidence} reason={up.reason}")
    print(f"downtrend: {down.direction} confidence={down.confidence} reason={down.reason}")
    print(f"flat: {flat.direction} reason={flat.reason}")
    print(f"short: {short.direction} reason={short.reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
