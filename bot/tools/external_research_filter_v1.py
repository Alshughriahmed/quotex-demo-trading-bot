from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

BOT_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BOT_DIR / "data.db"

BAD_ASSETS = {
    "NZD/CAD", "GBP/NZD", "CAD/CHF", "AUD/USD", "USD/BDT",
    "EUR/USD", "NZD/JPY", "USD/CHF", "CAD/JPY",
}
BAD_HOURS = {"07", "12", "23", "17", "14", "09", "22", "08"}

ALLOW_COMBOS = {
    ("USD/CAD", "CALL"),
    ("USD/JPY", "CALL"),
    ("USD/PKR", "PUT"),
    ("NZD/USD", "PUT"),
}


def connect() -> sqlite3.Connection:
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    return db


def rows_to_list(values: set[str]) -> list[str]:
    return sorted(values)


def placeholders(values: list[str]) -> str:
    return ",".join("?" for _ in values)


def metrics(db: sqlite3.Connection, title: str, where_sql: str = "1=1", params: tuple[Any, ...] = ()) -> sqlite3.Row:
    return db.execute(
        f"""
        SELECT ? AS filter_name,
               COUNT(*) AS trades,
               SUM(CASE WHEN result='WIN' THEN 1 ELSE 0 END) AS wins,
               SUM(CASE WHEN result='LOSS' THEN 1 ELSE 0 END) AS losses,
               SUM(CASE WHEN result='DRAW' THEN 1 ELSE 0 END) AS draws,
               ROUND(100.0 * SUM(CASE WHEN result='WIN' THEN 1 ELSE 0 END) /
                    NULLIF(SUM(CASE WHEN result IN ('WIN','LOSS','DRAW') THEN 1 ELSE 0 END), 0), 1) AS win_rate,
               ROUND(SUM(COALESCE(profit_loss, 0)), 2) AS profit_loss,
               ROUND(AVG(COALESCE(profit_loss, 0)), 2) AS avg_profit
        FROM external_trades
        WHERE {where_sql}
        """,
        (title, *params),
    ).fetchone()


def print_rows(title: str, rows: list[sqlite3.Row], columns: list[str]) -> None:
    print("-" * 72)
    print(title)
    print("-" * 72)
    print(" | ".join(columns))
    print(" | ".join("-" * len(c) for c in columns))
    for row in rows:
        print(" | ".join("" if row[c] is None else str(row[c]) for c in columns))


def combo_condition() -> tuple[str, list[str]]:
    parts = []
    params: list[str] = []
    for asset, direction in sorted(ALLOW_COMBOS):
        parts.append("(asset=? AND direction=?)")
        params.extend([asset, direction])
    return "(" + " OR ".join(parts) + ")", params


def main() -> int:
    print("=" * 72)
    print("QTB external research filter v1")
    print("=" * 72)
    print("This is a research report only. It reads external_* tables and does not modify native trades.")
    print(f"Database: {DB_PATH}")

    if not DB_PATH.exists():
        print("Database not found.")
        return 1

    bad_assets = rows_to_list(BAD_ASSETS)
    bad_hours = rows_to_list(BAD_HOURS)
    asset_ph = placeholders(bad_assets)
    hour_ph = placeholders(bad_hours)
    combo_sql, combo_params = combo_condition()

    with connect() as db:
        all_rows = [
            metrics(db, "baseline_all_external"),
            metrics(db, "exclude_bad_assets", f"asset NOT IN ({asset_ph})", tuple(bad_assets)),
            metrics(db, "exclude_bad_hours", f"strftime('%H', entry_time) NOT IN ({hour_ph})", tuple(bad_hours)),
            metrics(db, "exclude_bad_assets_and_hours", f"asset NOT IN ({asset_ph}) AND strftime('%H', entry_time) NOT IN ({hour_ph})", tuple(bad_assets + bad_hours)),
            metrics(db, "only_researched_asset_direction_combos", combo_sql, tuple(combo_params)),
            metrics(db, "combos_plus_no_bad_hours", f"{combo_sql} AND strftime('%H', entry_time) NOT IN ({hour_ph})", tuple(combo_params + bad_hours)),
        ]

        print_rows(
            "Filter comparison",
            all_rows,
            ["filter_name", "trades", "wins", "losses", "draws", "win_rate", "profit_loss", "avg_profit"],
        )

        print("-" * 72)
        print("Research filter v1 ingredients")
        print("-" * 72)
        print("Bad assets excluded:", ", ".join(bad_assets))
        print("Bad UTC hours excluded:", ", ".join(bad_hours))
        print("Allowed asset/direction combos:", ", ".join(f"{a} {d}" for a, d in sorted(ALLOW_COMBOS)))

        print("-" * 72)
        print("Decision")
        print("-" * 72)
        print("Use the best-looking row only as a research hypothesis.")
        print("Next validation must be on real replay candles or newer out-of-sample data, not on this same external history.")

    print("=" * 72)
    print("Research filter v1 finished. No native trades were changed.")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
