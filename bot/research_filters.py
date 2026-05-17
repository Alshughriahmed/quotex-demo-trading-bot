from __future__ import annotations

from dataclasses import dataclass


BAD_ASSETS = {
    "NZD/CAD",
    "GBP/NZD",
    "CAD/CHF",
    "AUD/USD",
    "USD/BDT",
    "EUR/USD",
    "NZD/JPY",
    "USD/CHF",
    "CAD/JPY",
}

BAD_UTC_HOURS = {"07", "08", "09", "12", "14", "17", "22", "23"}

CALL_ALLOWED_ASSETS = {"USD/CAD", "USD/JPY"}

FILTER_NAME = "research_candidate_conservative_v1"
FILTER_VERSION = "2026-05-17"


@dataclass(frozen=True)
class FilterDecision:
    allowed: bool
    reason: str


def normalize_hour(hour_utc: int | str | None) -> str:
    if hour_utc is None:
        return ""
    text = str(hour_utc).strip()
    if not text:
        return ""
    try:
        return f"{int(text):02d}"
    except ValueError:
        return text.zfill(2)


def evaluate_research_candidate(asset: str | None, direction: str | None, hour_utc: int | str | None) -> FilterDecision:
    """Research-only filter candidate derived from external historical analysis.

    This filter must not be treated as a live trading permission.
    It is a hypothesis that requires replay validation and signal-only validation.
    """
    asset_text = str(asset or "").strip().upper()
    direction_text = str(direction or "").strip().upper()
    hour_text = normalize_hour(hour_utc)

    if not asset_text:
        return FilterDecision(False, "missing_asset")
    if not direction_text:
        return FilterDecision(False, "missing_direction")
    if not hour_text:
        return FilterDecision(False, "missing_hour")

    if asset_text in BAD_ASSETS:
        return FilterDecision(False, "blocked_bad_asset")
    if hour_text in BAD_UTC_HOURS:
        return FilterDecision(False, "blocked_bad_utc_hour")
    if direction_text == "CALL" and asset_text not in CALL_ALLOWED_ASSETS:
        return FilterDecision(False, "blocked_call_asset_not_whitelisted")
    if direction_text not in {"CALL", "PUT"}:
        return FilterDecision(False, "blocked_unknown_direction")

    return FilterDecision(True, "allowed_research_candidate")


def filter_summary() -> dict[str, object]:
    return {
        "name": FILTER_NAME,
        "version": FILTER_VERSION,
        "bad_assets": sorted(BAD_ASSETS),
        "bad_utc_hours": sorted(BAD_UTC_HOURS),
        "call_allowed_assets": sorted(CALL_ALLOWED_ASSETS),
        "important_note": "Research-only candidate. Not a live trading permission.",
    }
