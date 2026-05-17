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
    original_profit: float
    inverse_profit: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read-only replay counterfactual diagnostics.")
    parser.add_argument("--strategy-version", default="", help="Optional strategy_version filter.")
    parser.add_argument("--asset", default="", help="Optional asset filter, for example USD/CAD.")
    parser.add_argument("--payout", type=float, default=0.80, help="Theoretical payout used for inverse simulation.")
    parser.add_argument("--min-trades", type=int, default=MIN_TRADES_DEFAULT, help="Minimum trades for ranked buckets.")
    parser.add_argument("--top", type=int, default=TOP_DEFAULT, help="Number of top rows to print.")
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


def inverse_profit(result: str, payout: float) -> float:
    if result == "WIN":
        return -1.0
    if result == "LOSS":
        return payout
    return 0.0


def load_rows(db: sqlite3.Connection, strategy_version: str, asset: str, payout: float) -> list[ReplayRow]:
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
        result = str(row["result"] or "UNKNOWN")
        loaded.append(
            ReplayRow(
                strategy_version=str(row["strategy_version"] or "unknown"),
                source_key=str(row["source_key"] or "unknown"),
                asset=str(row["asset"] or "unknown"),
                month=month,
                weekday=weekday,
                hour=hour,
                direction=str(row["direction"] or ""),
                result=result,
                original_profit=float(row["profit_loss"] or 0),
                inverse_profit=inverse_profit(result, payout),
            )
        )
    return loaded


def group_by(rows: Iterable[ReplayRow], key_func: Callable[[ReplayRow], tuple[str, ...]]) -> dict[tuple[str, ...], list[ReplayRow]]:
    grouped: dict[tuple[str, ...], list[ReplayRow]] = defaultdict(list)
    for row in rows:
        grouped[key_func(row)].append(row)
    return dict(grouped)


def metrics(rows: list[ReplayRow], mode: str) -> dict[str, object]:
    trades = len(rows)
    wins = sum(1 for r in rows if r.result == "WIN")
    losses = sum(1 for r in rows if r.result == "LOSS")
    draws = sum(1 for r in rows if r.result == "DRAW")
    original_profit = round(sum(r.original_profit for r in rows), 2)
    inverse_profit_value = round(sum(r.inverse_profit for r in rows), 2)
    original_win_rate = round(wins / (wins + losses + draws) * 100, 2) if (wins + losses + draws) else 0.0
    inverse_wins = losses
    inverse_losses = wins
    inverse_win_rate = round(inverse_wins / (wins + losses + draws) * 100, 2) if (wins + losses + draws) else 0.0
    if mode == "inverse":
        profit = inverse_profit_value
        win_rate = inverse_win_rate
        mode_wins = inverse_wins
        mode_losses = inverse_losses
    else:
        profit = original_profit
        win_rate = original_win_rate
        mode_wins = wins
        mode_losses = losses
    return {
        "trades": trades,
        "wins": mode_wins,
        "losses": mode_losses,
        "draws": draws,
        "win_rate": win_rate,
        "profit_loss": profit,
        "avg_profit": round(profit / trades, 4) if trades else 0.0,
        "original_profit": original_profit,
        "inverse_profit": inverse_profit_value,
    }


def fnum(value: object, digits: int = 2) -> str:
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return str(value)


def fpct(value: object) -> str:
    return f"{float(value or 0):.2f}%"


def status(m: dict[str, object], min_trades: int, months: int | None = None, loss_months: int | None = None) -> str:
    if int(m["trades"]) < min_trades:
        return "SMALL_SAMPLE"
    if float(m["profit_loss"]) <= 0:
        return "REJECT_NOW"
    if months is not None and loss_months is not None:
        if months >= 3 and loss_months == 0 and float(m["win_rate"]) >= 52:
            return "COUNTERFACTUAL_CANDIDATE"
        return "WATCH_ONLY"
    if float(m["win_rate"]) >= 52:
        return "COUNTERFACTUAL_POSITIVE"
    return "WATCH_ONLY"


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


def metric_row(name: str, rows: list[ReplayRow], mode: str, min_trades: int) -> dict[str, object]:
    m = metrics(rows, mode)
    return {
        "bucket": name,
        "mode": mode,
        "trades": m["trades"],
        "wins": m["wins"],
        "losses": m["losses"],
        "draws": m["draws"],
        "win_rate": fpct(m["win_rate"]),
        "profit_loss": fnum(m["profit_loss"]),
        "avg_profit": fnum(m["avg_profit"], 4),
        "original_pl": fnum(m["original_profit"]),
        "inverse_pl": fnum(m["inverse_profit"]),
        "status": status(m, min_trades),
    }


def print_ranked(title: str, rows: list[ReplayRow], key_func: Callable[[ReplayRow], tuple[str, ...]], key_label: Callable[[tuple[str, ...]], str], min_trades: int, top: int) -> None:
    section(title)
    grouped = group_by(rows, key_func)
    original_rows = [metric_row(key_label(key), bucket_rows, "original", min_trades) for key, bucket_rows in grouped.items()]
    inverse_rows = [metric_row(key_label(key), bucket_rows, "inverse", min_trades) for key, bucket_rows in grouped.items()]
    all_rows = [r for r in original_rows + inverse_rows if int(r["trades"]) >= min_trades]
    if not all_rows:
        print(f"No buckets with at least {min_trades} trades.")
        return
    all_rows.sort(key=lambda r: (float(str(r["profit_loss"])), float(str(r["win_rate"]).replace('%', ''))), reverse=True)
    table(
        ["bucket", "mode", "trades", "wins", "losses", "draws", "win_rate", "profit_loss", "avg_profit", "original_pl", "inverse_pl", "status"],
        all_rows[:top],
    )


def print_stability(title: str, rows: list[ReplayRow], combo_func: Callable[[ReplayRow], str], min_trades: int, top: int) -> None:
    section(title)
    by_version_combo = group_by(rows, lambda r: (r.strategy_version, combo_func(r)))
    output: list[dict[str, object]] = []
    for (strategy_version, combo), combo_rows in by_version_combo.items():
        for mode in ["original", "inverse"]:
            total = metrics(combo_rows, mode)
            if int(total["trades"]) < min_trades:
                continue
            by_month = group_by(combo_rows, lambda r: (r.month,))
            month_metrics = {month_key[0]: metrics(month_rows, mode) for month_key, month_rows in by_month.items()}
            months = len(month_metrics)
            win_months = sum(1 for m in month_metrics.values() if float(m["profit_loss"]) > 0)
            loss_months = sum(1 for m in month_metrics.values() if float(m["profit_loss"]) < 0)
            flat_months = sum(1 for m in month_metrics.values() if float(m["profit_loss"]) == 0)
            min_month_trades = min((int(m["trades"]) for m in month_metrics.values()), default=0)
            best_month = max(month_metrics, key=lambda k: float(month_metrics[k]["profit_loss"])) if month_metrics else ""
            worst_month = min(month_metrics, key=lambda k: float(month_metrics[k]["profit_loss"])) if month_metrics else ""
            output.append(
                {
                    "strategy_version": strategy_version,
                    "combo": combo,
                    "mode": mode,
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
                    "status": status(total, min_trades, months, loss_months),
                }
            )
    if not output:
        print(f"No buckets with at least {min_trades} trades.")
        return
    order = {"COUNTERFACTUAL_CANDIDATE": 0, "COUNTERFACTUAL_POSITIVE": 1, "WATCH_ONLY": 2, "REJECT_NOW": 3, "SMALL_SAMPLE": 4}
    output.sort(key=lambda r: (order.get(str(r["status"]), 9), -float(str(r["profit_loss"]))))
    table(
        ["strategy_version", "combo", "mode", "months", "win_months", "loss_months", "flat_months", "min_month_trades", "trades", "win_rate", "profit_loss", "best_month", "worst_month", "status"],
        output[:top * 2],
    )


def main() -> int:
    args = parse_args()
    payout = max(0.0, min(1.0, float(args.payout)))
    min_trades = max(1, int(args.min_trades or MIN_TRADES_DEFAULT))
    top = max(1, int(args.top or TOP_DEFAULT))

    print("=" * 96)
    print("QTB replay counterfactual report")
    print("=" * 96)
    print("This is read-only. It simulates original vs inverse direction outcomes from stored replay results.")
    print("It does not start the bot, does not connect to a broker, does not trade, and does not modify data.")
    print("Counterfactual positives are research hints only, not trading permission.")
    print(f"Database: {DB_PATH}")
    print(f"Strategy filter: {args.strategy_version.strip() or 'ALL'}")
    print(f"Asset filter: {args.asset.strip() or 'ALL'}")
    print(f"Theoretical payout: {payout:.2f}")
    print(f"Minimum trades per bucket: {min_trades}")

    if not DB_PATH.exists():
        print("Database not found. Run safe replay research tools first.")
        return 1

    with connect_read_only() as db:
        missing = [name for name in ["research_signals", "research_signal_outcomes"] if not table_exists(db, name)]
        if missing:
            print(f"Missing research tables: {', '.join(missing)}")
            return 1
        rows = load_rows(db, args.strategy_version.strip(), args.asset.strip(), payout)
        section("Overview")
        print(f"Total research_signals rows: {count_rows(db, 'research_signals')}")
        print(f"Total research_signal_outcomes rows: {count_rows(db, 'research_signal_outcomes')}")
        print(f"Loaded evaluated CALL/PUT rows after filters: {len(rows)}")
        print(f"Strategy versions loaded: {', '.join(sorted({r.strategy_version for r in rows})) if rows else 'none'}")
        print(f"Months loaded: {', '.join(sorted({r.month for r in rows})) if rows else 'none'}")
        if not rows:
            section("Conclusion")
            print("No evaluated CALL/PUT rows matched the filters.")
            return 0

        print_ranked(
            "Original vs inverse by strategy version",
            rows,
            lambda r: (r.strategy_version,),
            lambda k: k[0],
            min_trades,
            top,
        )
        print_ranked(
            "Original vs inverse by direction",
            rows,
            lambda r: (r.strategy_version, r.direction),
            lambda k: f"{k[0]} | {k[1]}",
            min_trades,
            top,
        )
        print_ranked(
            "Original vs inverse by hour",
            rows,
            lambda r: (r.strategy_version, r.hour),
            lambda k: f"{k[0]} | hour={k[1]}",
            min_trades,
            top,
        )
        print_ranked(
            "Original vs inverse by direction + hour",
            rows,
            lambda r: (r.strategy_version, r.direction, r.hour),
            lambda k: f"{k[0]} | {k[1]} | hour={k[2]}",
            min_trades,
            top,
        )
        print_stability(
            "Stability: direction + hour original/inverse",
            rows,
            lambda r: f"{r.direction}|hour={r.hour}",
            min_trades,
            top,
        )
        print_stability(
            "Stability: weekday original/inverse",
            rows,
            lambda r: f"weekday={r.weekday}",
            min_trades,
            top,
        )

        section("Conclusion")
        print("Counterfactual report finished. Use this only to decide whether redesign should explore inverse logic.")
        print("If inverse is also negative, the current signal timing/entry logic is weak, not merely reversed.")
        print("If an inverse bucket is positive but unstable by month, it remains WATCH_ONLY.")

    print("=" * 96)
    print("Replay counterfactual report finished. No native trades were changed.")
    print("=" * 96)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
