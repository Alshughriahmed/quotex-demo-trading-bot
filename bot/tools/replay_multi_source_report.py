from __future__ import annotations

import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

BOT_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BOT_DIR / "data.db"

MIN_TOTAL_TRADES = 100
MIN_MONTH_TRADES = 15
ONE_MONTH_DEPENDENCY_RATIO = 0.70
POSITIVE_HOURS = {"08", "09", "15"}


@dataclass(frozen=True)
class ReplayRow:
    strategy_version: str
    source_key: str
    asset: str
    month: str
    direction: str
    hour: str
    result: str
    profit: float


@dataclass(frozen=True)
class Rule:
    name: str
    note: str
    keep: Callable[[ReplayRow], bool]


def connect_read_only() -> sqlite3.Connection:
    db = sqlite3.connect(DB_PATH.resolve().as_uri() + "?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA query_only = ON")
    return db


def table_exists(db: sqlite3.Connection, name: str) -> bool:
    return db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None


def count_rows(db: sqlite3.Connection, table: str) -> int:
    return int(db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] or 0)


def scalar(db: sqlite3.Connection, query: str, params: tuple[object, ...] = ()) -> object:
    row = db.execute(query, params).fetchone()
    return row[0] if row else None


def parse_time(value: str) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc)
    return parsed


def month_of(value: str) -> str:
    parsed = parse_time(value)
    if parsed:
        return parsed.strftime("%Y-%m")
    return str(value or "")[:7] if len(str(value or "")) >= 7 else "unknown"


def hour_of(value: str) -> str:
    parsed = parse_time(value)
    if parsed:
        return f"{parsed.hour:02d}"
    return str(value or "")[11:13] if len(str(value or "")) >= 13 else ""


def rules() -> list[Rule]:
    return [
        Rule("baseline_all", "all evaluated replay signals", lambda r: True),
        Rule("only_put", "PUT only", lambda r: r.direction == "PUT"),
        Rule("only_call", "CALL only", lambda r: r.direction == "CALL"),
        Rule("only_hours_08_09_15", "signals only during UTC hours 08/09/15", lambda r: r.hour in POSITIVE_HOURS),
        Rule("put_hours_08_09_15", "PUT only during UTC hours 08/09/15", lambda r: r.direction == "PUT" and r.hour in POSITIVE_HOURS),
        Rule("put_hours_08_15", "PUT only during UTC hours 08/15", lambda r: r.direction == "PUT" and r.hour in {"08", "15"}),
        Rule("only_hours_15_08_09", "same hours as 08/09/15, kept for older report comparison", lambda r: r.hour in POSITIVE_HOURS),
        Rule("exclude_hours_12_17", "exclude UTC hours 12/17", lambda r: r.hour not in {"12", "17"}),
        Rule("put_exclude_hours_12_17", "PUT only while excluding UTC hours 12/17", lambda r: r.direction == "PUT" and r.hour not in {"12", "17"}),
    ]


def load_rows(db: sqlite3.Connection) -> list[ReplayRow]:
    rows = db.execute(
        """
        SELECT COALESCE(s.strategy_version, 'unknown') AS strategy_version,
               s.source_key,
               s.asset,
               s.direction,
               COALESCE(s.entry_time, s.signal_time) AS event_time,
               o.result,
               COALESCE(o.theoretical_profit_loss, 0) AS profit_loss
        FROM research_signals s
        JOIN research_signal_outcomes o ON o.signal_id = s.id
        WHERE s.direction IN ('CALL', 'PUT')
        ORDER BY COALESCE(s.strategy_version, 'unknown'),
                 s.source_key,
                 s.asset,
                 COALESCE(s.entry_time, s.signal_time),
                 s.id
        """
    ).fetchall()
    loaded: list[ReplayRow] = []
    for row in rows:
        event_time = str(row["event_time"] or "")
        loaded.append(
            ReplayRow(
                strategy_version=str(row["strategy_version"] or "unknown"),
                source_key=str(row["source_key"] or "unknown"),
                asset=str(row["asset"] or "unknown"),
                month=month_of(event_time),
                direction=str(row["direction"] or ""),
                hour=hour_of(event_time),
                result=str(row["result"] or "UNKNOWN"),
                profit=float(row["profit_loss"] or 0),
            )
        )
    return loaded


def candle_counts(db: sqlite3.Connection) -> dict[tuple[str, str, str], int]:
    rows = db.execute(
        """
        SELECT source_key, asset, substr(candle_time, 1, 7) AS month, COUNT(*) AS candles
        FROM research_market_candles
        GROUP BY source_key, asset, substr(candle_time, 1, 7)
        ORDER BY source_key, asset, month
        """
    ).fetchall()
    return {
        (str(r["source_key"] or "unknown"), str(r["asset"] or "unknown"), str(r["month"] or "unknown")): int(r["candles"] or 0)
        for r in rows
    }


def group_rows(rows: list[ReplayRow]) -> dict[tuple[str, str, str, str], list[ReplayRow]]:
    grouped: dict[tuple[str, str, str, str], list[ReplayRow]] = defaultdict(list)
    for row in rows:
        grouped[(row.strategy_version, row.source_key, row.asset, row.month)].append(row)
    return dict(grouped)


def metrics(rows: list[ReplayRow]) -> dict[str, object]:
    trades = len(rows)
    wins = sum(1 for r in rows if r.result == "WIN")
    losses = sum(1 for r in rows if r.result == "LOSS")
    draws = sum(1 for r in rows if r.result == "DRAW")
    unknown = sum(1 for r in rows if r.result == "UNKNOWN")
    evaluated = wins + losses + draws
    profit = round(sum(r.profit for r in rows), 2)
    win_rate = round((wins / evaluated) * 100, 2) if evaluated else 0.0
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
        "status": group_status(trades, win_rate, profit),
    }


def group_status(trades: int, win_rate: float, profit: float) -> str:
    if trades == 0:
        return "REJECT_NOW"
    if trades < MIN_MONTH_TRADES:
        return "WATCH_ONLY"
    if profit > 0 and win_rate >= 52:
        return "RESEARCH_KEEP"
    if profit > 0:
        return "WATCH_ONLY"
    return "REJECT_NOW"


def group_label(key: tuple[str, str, str, str] | None) -> str:
    if key is None:
        return "n/a"
    strategy_version, source_key, asset, month = key
    return f"strategy={strategy_version}; source={source_key}; asset={asset}; month={month}"


def fnum(value: float | int) -> str:
    return f"{float(value):.2f}"


def fpct(value: float | int) -> str:
    return f"{float(value):.2f}%"


def section(title: str) -> None:
    print("-" * 80)
    print(title)
    print("-" * 80)


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


def stability_status(months: int, win_months: int, trades: int, profit: float, depends_on_one_month: bool, small_sample: bool) -> str:
    if months == 0 or trades == 0 or profit <= 0:
        return "REJECT_NOW"
    if months < 2:
        return "WATCH_ONLY"
    if small_sample or depends_on_one_month:
        return "WATCH_ONLY"
    if months >= 3 and win_months / months >= 0.75:
        return "RESEARCH_KEEP"
    return "WATCH_ONLY"


def build_reports(
    grouped: dict[tuple[str, str, str, str], list[ReplayRow]],
    rule_set: list[Rule],
) -> tuple[dict[str, dict[tuple[str, str, str, str], dict[str, object]]], list[dict[str, object]]]:
    by_rule: dict[str, dict[tuple[str, str, str, str], dict[str, object]]] = {rule.name: {} for rule in rule_set}
    for key, rows in grouped.items():
        for rule in rule_set:
            by_rule[rule.name][key] = metrics([row for row in rows if rule.keep(row)])

    stability: list[dict[str, object]] = []
    strategy_versions = sorted({key[0] for key in grouped})
    for strategy_version in strategy_versions:
        version_keys = [key for key in grouped if key[0] == strategy_version]
        for rule in rule_set:
            tested = {k: by_rule[rule.name][k] for k in version_keys if int(by_rule[rule.name][k]["trades"]) > 0}
            months = len(tested)
            win_months = sum(1 for m in tested.values() if float(m["profit_loss"]) > 0)
            loss_months = sum(1 for m in tested.values() if float(m["profit_loss"]) < 0)
            flat_months = sum(1 for m in tested.values() if float(m["profit_loss"]) == 0)
            trades = sum(int(m["trades"]) for m in tested.values())
            wins = sum(int(m["wins"]) for m in tested.values())
            losses = sum(int(m["losses"]) for m in tested.values())
            draws = sum(int(m["draws"]) for m in tested.values())
            profit = round(sum(float(m["profit_loss"]) for m in tested.values()), 2)
            evaluated = wins + losses + draws
            win_rate = round(wins / evaluated * 100, 2) if evaluated else 0.0
            best = max(tested, key=lambda k: float(tested[k]["profit_loss"])) if tested else None
            worst = min(tested, key=lambda k: float(tested[k]["profit_loss"])) if tested else None
            best_profit = float(tested[best]["profit_loss"]) if best else 0.0
            worst_profit = float(tested[worst]["profit_loss"]) if worst else 0.0
            positive_sum = sum(float(m["profit_loss"]) for m in tested.values() if float(m["profit_loss"]) > 0)
            one_month = (months == 1 and profit > 0) or (
                profit > 0 and positive_sum > 0 and best_profit / positive_sum >= ONE_MONTH_DEPENDENCY_RATIO
            )
            min_month_trades = min((int(m["trades"]) for m in tested.values()), default=0)
            small_sample = trades < MIN_TOTAL_TRADES or min_month_trades < MIN_MONTH_TRADES
            status = stability_status(months, win_months, trades, profit, one_month, small_sample)
            stability.append(
                {
                    "strategy_version": strategy_version,
                    "rule": rule.name,
                    "months": months,
                    "win_months": win_months,
                    "loss_months": loss_months,
                    "flat_months": flat_months,
                    "trades": trades,
                    "win_rate": fpct(win_rate),
                    "profit_loss": fnum(profit),
                    "best_group": group_label(best),
                    "best_pl": fnum(best_profit),
                    "worst_group": group_label(worst),
                    "worst_pl": fnum(worst_profit),
                    "one_group_dependency": "YES" if one_month else "NO",
                    "small_sample": "YES" if small_sample else "NO",
                    "status": status,
                }
            )
    order = {"RESEARCH_KEEP": 0, "WATCH_ONLY": 1, "REJECT_NOW": 2}
    stability.sort(key=lambda r: (str(r["strategy_version"]), order.get(str(r["status"]), 9), -float(str(r["profit_loss"]))))
    return by_rule, stability


def pending_outcomes(db: sqlite3.Connection) -> int:
    return int(
        scalar(
            db,
            """
            SELECT COUNT(*)
            FROM research_signals s
            LEFT JOIN research_signal_outcomes o ON o.signal_id = s.id
            WHERE o.id IS NULL
              AND s.direction IN ('CALL', 'PUT')
            """,
        )
        or 0
    )


def main() -> int:
    print("=" * 80)
    print("QTB replay multi-source report")
    print("=" * 80)
    print("This is a read-only replay research report.")
    print("It does not start the bot.")
    print("It does not connect to a broker.")
    print("It does not trade.")
    print("It does not modify native trades.")
    print("It does not print secrets.")
    print(f"Database: {DB_PATH}")

    if not DB_PATH.exists():
        print("Database not found. Run the safe research setup/import tools first.")
        return 1

    with connect_read_only() as db:
        missing = [name for name in ["research_market_candles", "research_signals", "research_signal_outcomes"] if not table_exists(db, name)]
        if missing:
            print(f"Missing research tables: {', '.join(missing)}")
            return 1

        rows = load_rows(db)
        grouped = group_rows(rows)
        candles = candle_counts(db)
        rule_set = rules()
        strategy_versions = sorted({row.strategy_version for row in rows})

        section("Replay research overview")
        print(f"Research candles: {count_rows(db, 'research_market_candles')}")
        print(f"Research signals: {count_rows(db, 'research_signals')}")
        print(f"Research outcomes: {count_rows(db, 'research_signal_outcomes')}")
        print(f"Evaluated CALL/PUT rows loaded: {len(rows)}")
        print(f"Pending CALL/PUT signals without outcome: {pending_outcomes(db)}")
        print(f"Detected candle groups: {len(candles)}")
        print(f"Detected outcome groups: {len(grouped)}")
        print(f"Detected strategy versions: {', '.join(strategy_versions) if strategy_versions else 'none'}")

        if not rows:
            section("Conclusion")
            print("No evaluated CALL/PUT replay outcomes were found yet.")
            return 0

        section("Detected candle groups")
        candle_table = []
        for key in sorted(candles):
            candle_table.append({"source_key": key[0], "asset": key[1], "month": key[2], "candles": candles.get(key, 0)})
        table(["source_key", "asset", "month", "candles"], candle_table)

        section("Detected outcome groups")
        outcome_table = []
        for key in sorted(grouped):
            strategy_version, source_key, asset, month = key
            outcome_table.append(
                {
                    "strategy_version": strategy_version,
                    "source_key": source_key,
                    "asset": asset,
                    "month": month,
                    "candles": candles.get((source_key, asset, month), 0),
                    "outcomes": len(grouped.get(key, [])),
                }
            )
        table(["strategy_version", "source_key", "asset", "month", "candles", "outcomes"], outcome_table)

        by_rule, stability = build_reports(grouped, rule_set)

        section("Per-group rule reports")
        for key in sorted(grouped):
            strategy_version, source_key, asset, month = key
            print()
            print(f"Group: strategy={strategy_version}; source={source_key}; asset={asset}; month={month}")
            rows_out = []
            for rule in rule_set:
                m = by_rule[rule.name][key]
                rows_out.append(
                    {
                        "rule": rule.name,
                        "trades": m["trades"],
                        "wins": m["wins"],
                        "losses": m["losses"],
                        "draws": m["draws"],
                        "unknown": m["unknown"],
                        "win_rate": fpct(float(m["win_rate"])),
                        "profit_loss": fnum(float(m["profit_loss"])),
                        "avg_profit": fnum(float(m["avg_profit"])),
                        "group_status": m["status"],
                    }
                )
            table(["rule", "trades", "wins", "losses", "draws", "unknown", "win_rate", "profit_loss", "avg_profit", "group_status"], rows_out)

        section("Rule stability by strategy version")
        table(
            [
                "strategy_version",
                "rule",
                "months",
                "win_months",
                "loss_months",
                "flat_months",
                "trades",
                "win_rate",
                "profit_loss",
                "best_group",
                "best_pl",
                "worst_group",
                "worst_pl",
                "one_group_dependency",
                "small_sample",
                "status",
            ],
            stability,
        )
        print()
        print("Status note: RESEARCH_KEEP means research-only. Not a trading permission.")
        print("Stability is scoped by strategy_version. Do not compare or combine different strategy versions as one rule.")
        print("Small sample thresholds: total trades < 100 or any tested group < 15 trades.")
        print("One-group dependency threshold: best positive group >= 70% of positive group profit.")

        section("Rule notes")
        for rule in rule_set:
            print(f"{rule.name}: {rule.note}")

        section("Conclusion")
        print(f"Outcome groups evaluated: {len(grouped)}")
        if len(strategy_versions) > 1:
            print("Multiple strategy versions detected. Treat each version separately before judging stability.")
            print("A rule that is positive in one version/month and negative in another is not validated.")
        if len(grouped) < 2:
            print("Only one outcome group is available. Positive rules are still single-group hypotheses.")
            print("Next step: add another same-version USD/CAD M1 month and rerun this report before trusting any filter.")
        else:
            print("Use the strategy-scoped stability table, not only total profit, to judge each rule.")
            print("A rule that wins overall but loses a group, depends on one group, or has a small sample remains WATCH_ONLY.")
        keep = [row for row in stability if row["status"] == "RESEARCH_KEEP"]
        watch = [row for row in stability if row["status"] == "WATCH_ONLY"]
        reject = [row for row in stability if row["status"] == "REJECT_NOW"]
        print(f"RESEARCH_KEEP rows: {len(keep)}")
        print(f"WATCH_ONLY rows: {len(watch)}")
        print(f"REJECT_NOW rows: {len(reject)}")
        if keep:
            print("Research-only candidates:")
            for row in keep[:5]:
                print(
                    f"- {row['strategy_version']} / {row['rule']}: "
                    f"P/L {row['profit_loss']} over {row['trades']} trades. "
                    "Research only. Not a trading permission."
                )
        elif watch:
            print("No strategy-scoped rule is strong enough for RESEARCH_KEEP yet. Best WATCH_ONLY rows need more same-version out-of-sample months.")
        else:
            print("No positive stable rule found. Current rules should be rejected or redesigned after more data.")
        print("No trading decision should be made from this report alone.")

    print("=" * 80)
    print("Replay multi-source report finished. No native trades were changed.")
    print("=" * 80)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
