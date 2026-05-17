from __future__ import annotations

import argparse
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable

BOT_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BOT_DIR / "data.db"

MIN_TRADES_DEFAULT = 100
TOP_DEFAULT = 12


@dataclass(frozen=True)
class ReplayRow:
    strategy_version: str
    source_key: str
    asset: str
    month: str
    weekday: str
    hour: str
    direction: str
    result: str
    profit: float
    confidence: float | None
    rsi: float | None
    adx: float | None
    atr: float | None
    volatility: float | None
    body_ratio: float | None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read-only diagnostics for replay signal outcomes.")
    parser.add_argument("--strategy-version", default="", help="Optional strategy_version filter.")
    parser.add_argument("--asset", default="", help="Optional asset filter, for example USD/CAD.")
    parser.add_argument("--min-trades", type=int, default=MIN_TRADES_DEFAULT, help="Minimum trades for ranked buckets.")
    parser.add_argument("--top", type=int, default=TOP_DEFAULT, help="Number of top/bottom buckets to print.")
    return parser.parse_args()


def connect_read_only() -> sqlite3.Connection:
    db = sqlite3.connect(DB_PATH.resolve().as_uri() + "?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA query_only = ON")
    return db


def table_exists(db: sqlite3.Connection, name: str) -> bool:
    return db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None


def count_rows(db: sqlite3.Connection, table: str) -> int:
    return int(db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] or 0)


def parse_time(value: str) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def as_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def load_rows(db: sqlite3.Connection, strategy_version: str, asset: str) -> list[ReplayRow]:
    where = ["s.direction IN ('CALL', 'PUT')"]
    params: list[object] = []
    if strategy_version:
        where.append("COALESCE(s.strategy_version, 'unknown') = ?")
        params.append(strategy_version)
    if asset:
        where.append("s.asset = ?")
        params.append(asset)

    rows = db.execute(
        f"""
        SELECT COALESCE(s.strategy_version, 'unknown') AS strategy_version,
               s.source_key,
               s.asset,
               s.direction,
               COALESCE(s.entry_time, s.signal_time) AS event_time,
               s.confidence,
               s.rsi,
               s.adx,
               s.atr,
               s.volatility,
               s.candle_body_ratio,
               o.result,
               COALESCE(o.theoretical_profit_loss, 0) AS profit_loss
        FROM research_signals s
        JOIN research_signal_outcomes o ON o.signal_id = s.id
        WHERE {' AND '.join(where)}
        ORDER BY COALESCE(s.strategy_version, 'unknown'), s.source_key, s.asset, COALESCE(s.entry_time, s.signal_time), s.id
        """,
        tuple(params),
    ).fetchall()

    loaded: list[ReplayRow] = []
    for row in rows:
        event_time = parse_time(str(row["event_time"] or ""))
        month = event_time.strftime("%Y-%m") if event_time else "unknown"
        weekday = event_time.strftime("%a") if event_time else "unknown"
        hour = f"{event_time.hour:02d}" if event_time else "unknown"
        loaded.append(
            ReplayRow(
                strategy_version=str(row["strategy_version"] or "unknown"),
                source_key=str(row["source_key"] or "unknown"),
                asset=str(row["asset"] or "unknown"),
                month=month,
                weekday=weekday,
                hour=hour,
                direction=str(row["direction"] or ""),
                result=str(row["result"] or "UNKNOWN"),
                profit=float(row["profit_loss"] or 0),
                confidence=as_float(row["confidence"]),
                rsi=as_float(row["rsi"]),
                adx=as_float(row["adx"]),
                atr=as_float(row["atr"]),
                volatility=as_float(row["volatility"]),
                body_ratio=as_float(row["candle_body_ratio"]),
            )
        )
    return loaded


def group_by(rows: Iterable[ReplayRow], key_func: Callable[[ReplayRow], tuple[str, ...]]) -> dict[tuple[str, ...], list[ReplayRow]]:
    grouped: dict[tuple[str, ...], list[ReplayRow]] = defaultdict(list)
    for row in rows:
        grouped[key_func(row)].append(row)
    return dict(grouped)


def avg(values: Iterable[float | None]) -> float | None:
    cleaned = [float(v) for v in values if v is not None]
    if not cleaned:
        return None
    return sum(cleaned) / len(cleaned)


def metrics(rows: list[ReplayRow]) -> dict[str, object]:
    trades = len(rows)
    wins = sum(1 for r in rows if r.result == "WIN")
    losses = sum(1 for r in rows if r.result == "LOSS")
    draws = sum(1 for r in rows if r.result == "DRAW")
    unknown = sum(1 for r in rows if r.result == "UNKNOWN")
    evaluated = wins + losses + draws
    profit = round(sum(r.profit for r in rows), 2)
    win_rate = round(wins / evaluated * 100, 2) if evaluated else 0.0
    avg_profit = round(profit / trades, 4) if trades else 0.0
    return {
        "trades": trades,
        "wins": wins,
        "losses": losses,
        "draws": draws,
        "unknown": unknown,
        "win_rate": win_rate,
        "profit_loss": profit,
        "avg_profit": avg_profit,
        "avg_confidence": avg(r.confidence for r in rows),
        "avg_rsi": avg(r.rsi for r in rows),
        "avg_adx": avg(r.adx for r in rows),
        "avg_body_ratio": avg(r.body_ratio for r in rows),
    }


def bucket_status(m: dict[str, object], min_trades: int) -> str:
    trades = int(m["trades"])
    profit = float(m["profit_loss"])
    win_rate = float(m["win_rate"])
    if trades < min_trades:
        return "SMALL_SAMPLE"
    if profit > 0 and win_rate >= 52:
        return "DIAGNOSTIC_POSITIVE"
    if profit > 0:
        return "WATCH_ONLY"
    return "REJECT_NOW"


def stability_status(months: int, win_months: int, loss_months: int, profit: float, win_rate: float, min_month_trades: int, min_trades: int) -> str:
    if months < 2 or min_month_trades < max(15, min_trades // 5):
        return "WATCH_ONLY" if profit > 0 else "REJECT_NOW"
    if profit <= 0:
        return "REJECT_NOW"
    if months >= 3 and loss_months == 0 and win_rate >= 52:
        return "DIAGNOSTIC_CANDIDATE"
    if win_months > loss_months and win_rate >= 52:
        return "WATCH_ONLY"
    return "WATCH_ONLY"


def fnum(value: object, digits: int = 2) -> str:
    if value is None:
        return ""
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return str(value)


def fpct(value: object) -> str:
    return f"{float(value or 0):.2f}%"


def section(title: str) -> None:
    print("-" * 96)
    print(title)
    print("-" * 96)


def table(columns: list[str], rows: list[dict[str, object]]) -> None:
    if not rows:
        print("No data.")
        return
    rendered = [{col: str(row.get(col, "")) for col in columns} for row in rows]
    widths = {col: max(len(col), *(len(row[col]) for row in rendered)) for col in columns}
    print(" | ".join(col.ljust(widths[col]) for col in columns))
    print(" | ".join("-" * widths[col] for col in columns))
    for row in rendered:
        print(" | ".join(row[col].ljust(widths[col]) for col in columns))


def make_metric_row(name: str, rows: list[ReplayRow], min_trades: int) -> dict[str, object]:
    m = metrics(rows)
    return {
        "bucket": name,
        "trades": m["trades"],
        "wins": m["wins"],
        "losses": m["losses"],
        "draws": m["draws"],
        "win_rate": fpct(m["win_rate"]),
        "profit_loss": fnum(m["profit_loss"]),
        "avg_profit": fnum(m["avg_profit"], 4),
        "avg_conf": fnum(m["avg_confidence"]),
        "avg_rsi": fnum(m["avg_rsi"]),
        "avg_adx": fnum(m["avg_adx"]),
        "status": bucket_status(m, min_trades),
    }


def print_group_summary(title: str, rows: list[ReplayRow], key_func: Callable[[ReplayRow], tuple[str, ...]], key_label: Callable[[tuple[str, ...]], str], min_trades: int, top: int) -> None:
    section(title)
    grouped = group_by(rows, key_func)
    all_rows = [make_metric_row(key_label(key), bucket_rows, min_trades) for key, bucket_rows in grouped.items()]
    eligible = [r for r in all_rows if int(r["trades"]) >= min_trades]
    if not eligible:
        print(f"No buckets with at least {min_trades} trades.")
        return
    eligible.sort(key=lambda r: (float(str(r["profit_loss"])), float(str(r["win_rate"]).replace('%', ''))), reverse=True)
    print("Top buckets by theoretical P/L")
    table(["bucket", "trades", "wins", "losses", "draws", "win_rate", "profit_loss", "avg_profit", "avg_conf", "avg_rsi", "avg_adx", "status"], eligible[:top])
    print()
    print("Worst buckets by theoretical P/L")
    table(["bucket", "trades", "wins", "losses", "draws", "win_rate", "profit_loss", "avg_profit", "avg_conf", "avg_rsi", "avg_adx", "status"], list(reversed(eligible[-top:])))


def stability_table(rows: list[ReplayRow], label: str, combo_func: Callable[[ReplayRow], str], min_trades: int, top: int) -> None:
    section(f"Stability diagnostics: {label}")
    by_version_combo = group_by(rows, lambda r: (r.strategy_version, combo_func(r)))
    output: list[dict[str, object]] = []
    for (strategy_version, combo), combo_rows in by_version_combo.items():
        month_groups = group_by(combo_rows, lambda r: (r.month,))
        month_metrics = {month_key[0]: metrics(month_rows) for month_key, month_rows in month_groups.items()}
        total = metrics(combo_rows)
        if int(total["trades"]) < min_trades:
            continue
        months = len(month_metrics)
        win_months = sum(1 for m in month_metrics.values() if float(m["profit_loss"]) > 0)
        loss_months = sum(1 for m in month_metrics.values() if float(m["profit_loss"]) < 0)
        flat_months = sum(1 for m in month_metrics.values() if float(m["profit_loss"]) == 0)
        min_month_trades = min((int(m["trades"]) for m in month_metrics.values()), default=0)
        best_month = max(month_metrics, key=lambda k: float(month_metrics[k]["profit_loss"])) if month_metrics else ""
        worst_month = min(month_metrics, key=lambda k: float(month_metrics[k]["profit_loss"])) if month_metrics else ""
        status = stability_status(
            months,
            win_months,
            loss_months,
            float(total["profit_loss"]),
            float(total["win_rate"]),
            min_month_trades,
            min_trades,
        )
        output.append(
            {
                "strategy_version": strategy_version,
                "combo": combo,
                "months": months,
                "win_months": win_months,
                "loss_months": loss_months,
                "flat_months": flat_months,
                "min_month_trades": min_month_trades,
                "trades": total["trades"],
                "win_rate": fpct(total["win_rate"]),
                "profit_loss": fnum(total["profit_loss"]),
                "best_month": f"{best_month} ({fnum(month_metrics[best_month]['profit_loss'])})" if best_month else "",
                "worst_month": f"{worst_month} ({fnum(month_metrics[worst_month]['profit_loss'])})" if worst_month else "",
                "status": status,
            }
        )
    if not output:
        print(f"No stable buckets with at least {min_trades} trades.")
        return
    order = {"DIAGNOSTIC_CANDIDATE": 0, "WATCH_ONLY": 1, "REJECT_NOW": 2}
    output.sort(key=lambda r: (order.get(str(r["status"]), 9), -float(str(r["profit_loss"]))))
    table(
        [
            "strategy_version",
            "combo",
            "months",
            "win_months",
            "loss_months",
            "flat_months",
            "min_month_trades",
            "trades",
            "win_rate",
            "profit_loss",
            "best_month",
            "worst_month",
            "status",
        ],
        output[:top * 2],
    )


def main() -> int:
    args = parse_args()
    min_trades = max(1, int(args.min_trades or MIN_TRADES_DEFAULT))
    top = max(1, int(args.top or TOP_DEFAULT))

    print("=" * 96)
    print("QTB replay diagnostics report")
    print("=" * 96)
    print("This is a read-only diagnostic report over stored replay research outcomes.")
    print("It does not start the bot, does not connect to a broker, does not trade, and does not modify data.")
    print("It is for pattern discovery only. Positive buckets are not trading permission.")
    print(f"Database: {DB_PATH}")
    print(f"Strategy filter: {args.strategy_version.strip() or 'ALL'}")
    print(f"Asset filter: {args.asset.strip() or 'ALL'}")
    print(f"Minimum trades per ranked bucket: {min_trades}")

    if not DB_PATH.exists():
        print("Database not found. Run the safe replay research tools first.")
        return 1

    with connect_read_only() as db:
        missing = [name for name in ["research_signals", "research_signal_outcomes"] if not table_exists(db, name)]
        if missing:
            print(f"Missing research tables: {', '.join(missing)}")
            return 1
        rows = load_rows(db, args.strategy_version.strip(), args.asset.strip())
        section("Overview")
        print(f"Total research_signals rows: {count_rows(db, 'research_signals')}")
        print(f"Total research_signal_outcomes rows: {count_rows(db, 'research_signal_outcomes')}")
        print(f"Loaded evaluated CALL/PUT rows after filters: {len(rows)}")
        print(f"Strategy versions loaded: {', '.join(sorted({r.strategy_version for r in rows})) if rows else 'none'}")
        print(f"Months loaded: {', '.join(sorted({r.month for r in rows})) if rows else 'none'}")

        if not rows:
            section("Conclusion")
            print("No evaluated CALL/PUT replay outcomes matched the filters.")
            return 0

        print_group_summary(
            "Strategy version summary",
            rows,
            lambda r: (r.strategy_version,),
            lambda k: k[0],
            min_trades,
            top,
        )
        print_group_summary(
            "Month summary by strategy version",
            rows,
            lambda r: (r.strategy_version, r.month),
            lambda k: f"{k[0]} | {k[1]}",
            min_trades,
            top,
        )
        print_group_summary(
            "Direction summary",
            rows,
            lambda r: (r.strategy_version, r.direction),
            lambda k: f"{k[0]} | {k[1]}",
            min_trades,
            top,
        )
        print_group_summary(
            "Hour summary",
            rows,
            lambda r: (r.strategy_version, r.hour),
            lambda k: f"{k[0]} | hour={k[1]}",
            min_trades,
            top,
        )
        print_group_summary(
            "Direction + hour combinations",
            rows,
            lambda r: (r.strategy_version, r.direction, r.hour),
            lambda k: f"{k[0]} | {k[1]} | hour={k[2]}",
            min_trades,
            top,
        )
        print_group_summary(
            "Weekday summary",
            rows,
            lambda r: (r.strategy_version, r.weekday),
            lambda k: f"{k[0]} | weekday={k[1]}",
            min_trades,
            top,
        )
        print_group_summary(
            "Direction + weekday combinations",
            rows,
            lambda r: (r.strategy_version, r.direction, r.weekday),
            lambda k: f"{k[0]} | {k[1]} | weekday={k[2]}",
            min_trades,
            top,
        )

        stability_table(rows, "hour", lambda r: f"hour={r.hour}", min_trades, top)
        stability_table(rows, "direction + hour", lambda r: f"{r.direction}|hour={r.hour}", min_trades, top)
        stability_table(rows, "weekday", lambda r: f"weekday={r.weekday}", min_trades, top)
        stability_table(rows, "direction + weekday", lambda r: f"{r.direction}|weekday={r.weekday}", min_trades, top)

        section("Conclusion")
        print("Diagnostics finished. Use this report to decide what to investigate next, not to trade.")
        print("A bucket is interesting only if it remains positive across multiple months inside the same strategy_version.")
        print("If no DIAGNOSTIC_CANDIDATE appears, redesign the strategy logic before testing more filters.")

    print("=" * 96)
    print("Replay diagnostics report finished. No native trades were changed.")
    print("=" * 96)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
