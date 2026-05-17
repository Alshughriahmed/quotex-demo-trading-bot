from __future__ import annotations

import re
import sqlite3
from collections import Counter
from pathlib import Path


BOT_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BOT_DIR / "data.db"
LOG_DIR = BOT_DIR / "logs"
TRADER_LOG = LOG_DIR / "trader.log"
QUOTEX_LOG = LOG_DIR / "quotex.log"

AUDIT_EVENT_RE = re.compile(r"AUDIT event=([^\s]+)")
DECISION_RE = re.compile(r"Decision asset=([^\s]+) direction=([^\s]+) confidence=(\d+)")


def read_tail(path: Path, max_lines: int = 400) -> list[str]:
    if not path.exists():
        return []
    try:
        return path.read_text(encoding="utf-8", errors="replace").splitlines()[-max_lines:]
    except OSError:
        return []


def db_summary() -> list[str]:
    lines: list[str] = []
    if not DB_PATH.exists():
        return [f"Database: missing ({DB_PATH})"]

    lines.append(f"Database: found ({DB_PATH})")
    with sqlite3.connect(DB_PATH) as db:
        db.row_factory = sqlite3.Row
        tables = {
            row["name"]
            for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }

        if "assets" in tables:
            row = db.execute(
                "SELECT COUNT(*) AS total, SUM(CASE WHEN enabled=1 THEN 1 ELSE 0 END) AS enabled FROM assets"
            ).fetchone()
            lines.append(f"Assets: total={row['total'] or 0}, enabled={row['enabled'] or 0}")

        if "trades" in tables:
            row = db.execute("SELECT COUNT(*) AS total FROM trades").fetchone()
            lines.append(f"Trades: total={row['total'] or 0}")
            rows = db.execute(
                "SELECT status, COUNT(*) AS total FROM trades GROUP BY status ORDER BY status"
            ).fetchall()
            if rows:
                lines.append("Trade status counts:")
                for item in rows:
                    lines.append(f"  - {item['status']}: {item['total']}")

        if "quotex_accounts" in tables:
            row = db.execute("SELECT email, password, account_type, enabled FROM quotex_accounts WHERE id=1").fetchone()
            if row:
                lines.append(
                    "Quotex local account: "
                    f"email={'configured' if row['email'] else 'missing'}, "
                    f"password={'configured' if row['password'] else 'missing'}, "
                    f"account_type={row['account_type'] or 'missing'}, "
                    f"enabled={row['enabled']}"
                )
            else:
                lines.append("Quotex local account: missing row")
    return lines


def log_summary() -> list[str]:
    lines: list[str] = []
    trader_lines = read_tail(TRADER_LOG)
    quotex_lines = read_tail(QUOTEX_LOG)

    lines.append(f"trader.log: {'found' if trader_lines else 'missing or empty'}")
    lines.append(f"quotex.log: {'found' if quotex_lines else 'missing or empty'}")

    events = Counter()
    decisions = Counter()
    warnings: list[str] = []
    errors: list[str] = []

    for line in trader_lines:
        event_match = AUDIT_EVENT_RE.search(line)
        if event_match:
            events[event_match.group(1)] += 1
        decision_match = DECISION_RE.search(line)
        if decision_match:
            asset, direction, confidence = decision_match.groups()
            decisions[f"{asset} {direction} {confidence}"] += 1
        if " ERROR " in line or "exception" in line.lower() or "failed" in line.lower():
            errors.append(line)
        elif " WARNING " in line or "missing" in line.lower():
            warnings.append(line)

    for line in quotex_lines:
        if " ERROR " in line or "exception" in line.lower() or "failed" in line.lower():
            errors.append(line)
        elif " WARNING " in line or "missing" in line.lower():
            warnings.append(line)

    if events:
        lines.append("Audit events in recent trader.log tail:")
        for event, count in events.most_common(20):
            lines.append(f"  - {event}: {count}")

    if decisions:
        lines.append("Recent strategy decisions:")
        for decision, count in decisions.most_common(10):
            lines.append(f"  - {decision}: {count}")

    if errors:
        lines.append("Recent errors/failures:")
        for item in errors[-8:]:
            lines.append(f"  - {trim(item)}")

    if warnings:
        lines.append("Recent warnings:")
        for item in warnings[-5:]:
            lines.append(f"  - {trim(item)}")

    if events.get("scan_started", 0) > 0 and events.get("asset_analyzed", 0) == 0:
        lines.append("Diagnosis hint: scans start, but no assets are analyzed yet.")
        lines.append("Most common causes: missing local Quotex DEMO credentials, Quotex connection failure, or candle fetch blocking/failing.")

    return lines


def trim(text: str, limit: int = 220) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def main() -> int:
    print("=" * 72)
    print("QTB local runtime diagnostics")
    print("=" * 72)
    print()

    for line in db_summary():
        print(line)

    print()
    print("-" * 72)
    print()

    for line in log_summary():
        print(line)

    print()
    print("=" * 72)
    print("Diagnostics finished. No secrets are printed by this tool.")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
