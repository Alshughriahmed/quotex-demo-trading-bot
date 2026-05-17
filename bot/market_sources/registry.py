from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class MarketSourceStatus:
    source_key: str
    label: str
    configured: bool
    enabled: bool
    safe_for_signal_only: bool
    reason: str

    @property
    def readiness(self) -> str:
        if not self.configured:
            return "missing"
        if not self.enabled:
            return "disabled"
        if self.safe_for_signal_only:
            return "signal_only_ready"
        return "not_ready"


def get_market_source_status(db_path: str | Path) -> MarketSourceStatus:
    """Return the current safe placeholder market-source status.

    This registry intentionally does not inspect or print any account fields.
    The current stage has no active market source configured. Future source
    adapters must keep data reading separate from order execution.
    """
    path = Path(db_path)
    if not path.exists():
        return MarketSourceStatus(
            source_key="none",
            label="No market source",
            configured=False,
            enabled=False,
            safe_for_signal_only=False,
            reason="database is missing",
        )

    return MarketSourceStatus(
        source_key="none",
        label="No market source",
        configured=False,
        enabled=False,
        safe_for_signal_only=False,
        reason="market source adapter is not configured yet",
    )
