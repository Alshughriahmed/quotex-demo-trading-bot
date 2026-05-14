from __future__ import annotations

from dataclasses import dataclass, field
from statistics import mean
from typing import Any


CALL = "CALL"
PUT = "PUT"
NO_TRADE = "NO_TRADE"


STRATEGY_PROFILES = {
    60: {
        "ema_fast": 5,
        "ema_slow": 13,
        "rsi_period": 7,
        "min_candles": 35,
        "min_confidence": 72,
    },
    120: {
        "ema_fast": 7,
        "ema_slow": 18,
        "rsi_period": 10,
        "min_candles": 45,
        "min_confidence": 74,
    },
    180: {
        "ema_fast": 9,
        "ema_slow": 21,
        "rsi_period": 14,
        "min_candles": 55,
        "min_confidence": 75,
    },
    300: {
        "ema_fast": 12,
        "ema_slow": 26,
        "rsi_period": 14,
        "min_candles": 75,
        "min_confidence": 76,
    },
    900: {
        "ema_fast": 20,
        "ema_slow": 50,
        "rsi_period": 14,
        "min_candles": 120,
        "min_confidence": 78,
    },
}


@dataclass(slots=True)
class StrategyDecision:
    asset: str
    direction: str
    confidence: int
    reason: str
    duration_seconds: int
    rsi: float | None = None
    ema_fast: float | None = None
    ema_slow: float | None = None
    trend: str | None = None
    volatility: float | None = None
    indicators: dict[str, Any] = field(default_factory=dict)

    @property
    def has_trade(self) -> bool:
        return self.direction in {CALL, PUT}


def analyze(
    asset: str,
    candles: list[dict[str, Any]],
    duration_seconds: int = 180,
    min_confidence: int | None = None,
    drop_open_candle: bool = True,
) -> StrategyDecision:
    profile = get_profile(duration_seconds)
    prepared = prepare_candles(candles, drop_open_candle=drop_open_candle)
    required = profile["min_candles"]
    if len(prepared) < required:
        return no_trade(asset, duration_seconds, f"شموع غير كافية: {len(prepared)}/{required}")

    closes = [c["close"] for c in prepared]
    opens = [c["open"] for c in prepared]
    highs = [c["high"] for c in prepared]
    lows = [c["low"] for c in prepared]

    ema_fast_values = ema_series(closes, profile["ema_fast"])
    ema_slow_values = ema_series(closes, profile["ema_slow"])
    rsi_value = rsi(closes, profile["rsi_period"])
    volatility = average_range_percent(highs, lows, closes, lookback=12)
    atr_value = atr(highs, lows, closes, period=14)
    adx_value = adx(highs, lows, closes, period=14)

    last = prepared[-1]
    previous = prepared[-2]
    ema_fast = ema_fast_values[-1]
    ema_slow = ema_slow_values[-1]
    ema_gap = abs(ema_fast - ema_slow)
    fast_slope = ema_fast_values[-1] - ema_fast_values[-4]
    slow_slope = ema_slow_values[-1] - ema_slow_values[-4]
    last_body_ratio = candle_body_ratio(last)
    previous_body_ratio = candle_body_ratio(previous)
    last_bullish = last["close"] > last["open"]
    last_bearish = last["close"] < last["open"]

    direction = detect_direction(ema_fast, ema_slow, fast_slope, slow_slope, last)
    if direction == NO_TRADE:
        return no_trade(
            asset,
            duration_seconds,
            "الاتجاه غير واضح",
            rsi_value,
            ema_fast,
            ema_slow,
            volatility,
        )

    confidence, reasons = score_signal(
        direction=direction,
        closes=closes,
        ema_fast=ema_fast,
        ema_slow=ema_slow,
        fast_slope=fast_slope,
        slow_slope=slow_slope,
        rsi_value=rsi_value,
        volatility=volatility,
        atr_value=atr_value,
        adx_value=adx_value,
        last_body_ratio=last_body_ratio,
        previous_body_ratio=previous_body_ratio,
        last_bullish=last_bullish,
        last_bearish=last_bearish,
    )
    threshold = min_confidence if min_confidence is not None else profile["min_confidence"]

    indicators = {
        "ema_fast_period": profile["ema_fast"],
        "ema_slow_period": profile["ema_slow"],
        "rsi_period": profile["rsi_period"],
        "last_body_ratio": round(last_body_ratio, 4),
        "previous_body_ratio": round(previous_body_ratio, 4),
        "ema_gap": round(ema_gap, 8),
        "atr": round(atr_value, 8),
        "adx": round(adx_value, 2),
        "fast_slope": round(fast_slope, 8),
        "slow_slope": round(slow_slope, 8),
        "threshold": threshold,
    }

    if confidence < threshold:
        return StrategyDecision(
            asset=asset,
            direction=NO_TRADE,
            confidence=confidence,
            reason=f"الثقة أقل من المطلوب: {confidence}/{threshold}",
            duration_seconds=duration_seconds,
            rsi=round(rsi_value, 2),
            ema_fast=ema_fast,
            ema_slow=ema_slow,
            trend=direction,
            volatility=volatility,
            indicators=indicators,
        )

    return StrategyDecision(
        asset=asset,
        direction=direction,
        confidence=confidence,
        reason=" + ".join(reasons),
        duration_seconds=duration_seconds,
        rsi=round(rsi_value, 2),
        ema_fast=ema_fast,
        ema_slow=ema_slow,
        trend=direction,
        volatility=volatility,
        indicators=indicators,
    )


def get_profile(duration_seconds: int) -> dict[str, int]:
    if duration_seconds in STRATEGY_PROFILES:
        return STRATEGY_PROFILES[duration_seconds]
    closest = min(STRATEGY_PROFILES, key=lambda key: abs(key - duration_seconds))
    return STRATEGY_PROFILES[closest]


def prepare_candles(candles: list[dict[str, Any]], drop_open_candle: bool = True) -> list[dict[str, float]]:
    prepared = []
    for candle in candles or []:
        item = normalize_candle(candle)
        if item:
            prepared.append(item)

    prepared.sort(key=lambda c: c.get("time") or 0)
    if drop_open_candle and len(prepared) > 2:
        prepared = prepared[:-1]
    return prepared


def normalize_candle(candle: dict[str, Any]) -> dict[str, float] | None:
    try:
        return {
            "time": float(candle.get("time") or candle.get("from") or candle.get("timestamp") or 0),
            "open": float(candle["open"]),
            "high": float(candle["high"]),
            "low": float(candle["low"]),
            "close": float(candle["close"]),
        }
    except (KeyError, TypeError, ValueError):
        return None


def detect_direction(ema_fast: float, ema_slow: float, fast_slope: float, slow_slope: float, last: dict[str, float]) -> str:
    if ema_fast > ema_slow and fast_slope > 0 and slow_slope >= 0 and last["close"] >= ema_fast:
        return CALL
    if ema_fast < ema_slow and fast_slope < 0 and slow_slope <= 0 and last["close"] <= ema_fast:
        return PUT
    return NO_TRADE


def score_signal(
    direction: str,
    closes: list[float],
    ema_fast: float,
    ema_slow: float,
    fast_slope: float,
    slow_slope: float,
    rsi_value: float,
    volatility: float,
    atr_value: float,
    adx_value: float,
    last_body_ratio: float,
    previous_body_ratio: float,
    last_bullish: bool,
    last_bearish: bool,
) -> tuple[int, list[str]]:
    score = 25
    cap = 100
    reasons = []
    trend_gap = abs(ema_fast - ema_slow) / closes[-1] if closes[-1] else 0
    atr_percent = atr_value / closes[-1] if closes[-1] else 0
    has_confirmation = False
    has_acceptable_rsi = False
    pressure_down = False

    if trend_gap > 0.00008:
        score += 10
        reasons.append("EMA trend")
    if abs(fast_slope) > abs(slow_slope):
        score += 7
        reasons.append("EMA momentum")

    if direction == CALL:
        if 45 <= rsi_value <= 68:
            score += 12
            reasons.append("RSI مناسب")
        elif 38 <= rsi_value < 45 or 68 < rsi_value <= 74:
            score += 4
            has_acceptable_rsi = True
            cap = min(cap, 86)
            reasons.append("RSI مقبول")
        if last_bullish and last_body_ratio >= 0.45:
            score += 10
            has_confirmation = True
            reasons.append("شمعة تأكيد")
    else:
        if 32 <= rsi_value <= 55:
            score += 12
            reasons.append("RSI مناسب")
        elif 26 <= rsi_value < 32 or 55 < rsi_value <= 62:
            score += 4
            has_acceptable_rsi = True
            cap = min(cap, 86)
            reasons.append("RSI مقبول")
        if last_bearish and last_body_ratio >= 0.45:
            score += 10
            has_confirmation = True
            reasons.append("شمعة تأكيد")

    if 0.00003 <= volatility <= 0.003:
        score += 6
        reasons.append("تذبذب مناسب")
    elif volatility > 0.006:
        score -= 15
        cap = min(cap, 78)
        reasons.append("تذبذب عالي")

    if last_body_ratio < 0.25 and previous_body_ratio < 0.25:
        score -= 20
        cap = min(cap, 80)
        reasons.append("شموع ضعيفة")

    if adx_value >= 25:
        score += 8
        reasons.append("ADX قوي")
    elif adx_value >= 18:
        score += 4
        cap = min(cap, 92)
        reasons.append("ADX مقبول")
    else:
        cap = min(cap, 90)

    if 0.00003 <= atr_percent <= 0.003:
        score += 5
        reasons.append("ATR مناسب")
    elif atr_percent > 0.006:
        score -= 10
        cap = min(cap, 80)
        reasons.append("ATR عالي")

    if trend_gap > 0.00016:
        score += 5
        reasons.append("EMA gap واضح")

    if last_body_ratio >= 0.62:
        score += 5
        reasons.append("جسم شمعة قوي")

    if direction == CALL and closes[-1] > closes[-2] > closes[-3]:
        score += 3
        reasons.append("ضغط صعود")
    if direction == PUT and closes[-1] < closes[-2] < closes[-3]:
        score -= 4
        pressure_down = True
        cap = min(cap, 88)
        reasons.append("ضغط هبوط")

    if not has_confirmation:
        cap = min(cap, 85)
    if has_acceptable_rsi and pressure_down:
        cap = min(cap, 84)

    return max(0, min(cap, int(round(score)))), reasons or ["إشارة أساسية"]


def ema_series(values: list[float], period: int) -> list[float]:
    if not values:
        return []
    multiplier = 2 / (period + 1)
    result = [values[0]]
    for value in values[1:]:
        result.append((value - result[-1]) * multiplier + result[-1])
    return result


def rsi(values: list[float], period: int = 14) -> float:
    if len(values) <= period:
        return 50.0

    gains = []
    losses = []
    for index in range(1, period + 1):
        change = values[index] - values[index - 1]
        gains.append(max(change, 0))
        losses.append(abs(min(change, 0)))

    average_gain = mean(gains)
    average_loss = mean(losses)

    for index in range(period + 1, len(values)):
        change = values[index] - values[index - 1]
        gain = max(change, 0)
        loss = abs(min(change, 0))
        average_gain = ((average_gain * (period - 1)) + gain) / period
        average_loss = ((average_loss * (period - 1)) + loss) / period

    if average_loss == 0:
        return 100.0
    relative_strength = average_gain / average_loss
    return 100 - (100 / (1 + relative_strength))


def average_range_percent(highs: list[float], lows: list[float], closes: list[float], lookback: int = 12) -> float:
    count = min(lookback, len(closes))
    if count <= 0:
        return 0.0
    ranges = []
    for high, low, close in zip(highs[-count:], lows[-count:], closes[-count:]):
        if close:
            ranges.append((high - low) / close)
    return mean(ranges) if ranges else 0.0


def atr(highs: list[float], lows: list[float], closes: list[float], period: int = 14) -> float:
    ranges = true_ranges(highs, lows, closes)
    if not ranges:
        return 0.0
    return mean(ranges[-period:])


def adx(highs: list[float], lows: list[float], closes: list[float], period: int = 14) -> float:
    if len(closes) <= period + 1:
        return 0.0

    true_range_values = []
    plus_dm_values = []
    minus_dm_values = []
    for index in range(1, len(closes)):
        high_diff = highs[index] - highs[index - 1]
        low_diff = lows[index - 1] - lows[index]
        plus_dm_values.append(high_diff if high_diff > low_diff and high_diff > 0 else 0.0)
        minus_dm_values.append(low_diff if low_diff > high_diff and low_diff > 0 else 0.0)
        true_range_values.append(max(
            highs[index] - lows[index],
            abs(highs[index] - closes[index - 1]),
            abs(lows[index] - closes[index - 1]),
        ))

    if len(true_range_values) < period:
        return 0.0

    smoothed_tr = sum(true_range_values[:period])
    smoothed_plus_dm = sum(plus_dm_values[:period])
    smoothed_minus_dm = sum(minus_dm_values[:period])
    dx_values = []

    if smoothed_tr > 0:
        plus_di = 100 * (smoothed_plus_dm / smoothed_tr)
        minus_di = 100 * (smoothed_minus_dm / smoothed_tr)
        total_di = plus_di + minus_di
        if total_di > 0:
            dx_values.append(100 * abs(plus_di - minus_di) / total_di)

    for index in range(period, len(true_range_values)):
        smoothed_tr = smoothed_tr - (smoothed_tr / period) + true_range_values[index]
        smoothed_plus_dm = smoothed_plus_dm - (smoothed_plus_dm / period) + plus_dm_values[index]
        smoothed_minus_dm = smoothed_minus_dm - (smoothed_minus_dm / period) + minus_dm_values[index]

        if smoothed_tr <= 0:
            continue
        plus_di = 100 * (smoothed_plus_dm / smoothed_tr)
        minus_di = 100 * (smoothed_minus_dm / smoothed_tr)
        total_di = plus_di + minus_di
        if total_di <= 0:
            continue
        dx_values.append(100 * abs(plus_di - minus_di) / total_di)

    if not dx_values:
        return 0.0
    return mean(dx_values[-period:])


def true_ranges(highs: list[float], lows: list[float], closes: list[float]) -> list[float]:
    if len(closes) < 2:
        return []
    ranges = []
    for index in range(1, len(closes)):
        ranges.append(max(
            highs[index] - lows[index],
            abs(highs[index] - closes[index - 1]),
            abs(lows[index] - closes[index - 1]),
        ))
    return ranges


def candle_body_ratio(candle: dict[str, float]) -> float:
    full_range = candle["high"] - candle["low"]
    if full_range <= 0:
        return 0.0
    return abs(candle["close"] - candle["open"]) / full_range


def no_trade(
    asset: str,
    duration_seconds: int,
    reason: str,
    rsi_value: float | None = None,
    ema_fast: float | None = None,
    ema_slow: float | None = None,
    volatility: float | None = None,
) -> StrategyDecision:
    return StrategyDecision(
        asset=asset,
        direction=NO_TRADE,
        confidence=0,
        reason=reason,
        duration_seconds=duration_seconds,
        rsi=round(rsi_value, 2) if rsi_value is not None else None,
        ema_fast=ema_fast,
        ema_slow=ema_slow,
        trend=NO_TRADE,
        volatility=volatility,
    )
