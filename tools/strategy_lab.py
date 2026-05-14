from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_portfolio_sweep(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if "results" not in data:
        raise ValueError("Expected a JSON report produced by sweep_portfolio.py")
    return data


def risk_flags(row: dict[str, Any]) -> list[str]:
    flags: list[str] = []
    loss_rate = float(row.get("loss_rate", 0) or 0)
    max_consecutive_losses = int(row.get("max_consecutive_losses", 0) or 0)
    max_drawdown_units = int(row.get("max_drawdown_units", 0) or 0)
    final_equity_units = int(row.get("final_equity_units", 0) or 0)

    if loss_rate > 45:
        flags.append("loss rate too high")
    if max_consecutive_losses > 5:
        flags.append("loss streak too long")
    if max_drawdown_units > 8:
        flags.append("drawdown too high")
    if final_equity_units <= 0:
        flags.append("non-positive final equity")
    return flags


def classify_row(row: dict[str, Any]) -> tuple[str, list[str]]:
    notes: list[str] = []
    win_rate = float(row.get("win_rate_excluding_draws", 0) or 0)
    closed = int(row.get("closed_trades", 0) or 0)
    files = int(row.get("files_tested", 0) or 0)
    worst = float(row.get("worst_file_score", 0) or 0)
    consistency = float(row.get("consistency_score", 0) or 0)
    final_equity_units = int(row.get("final_equity_units", 0) or 0)
    risks = risk_flags(row)

    if closed < 20:
        notes.append("sample too small")
    if files < 2:
        notes.append("tested on too few files")
    if worst <= 0:
        notes.append("weak worst-file behavior")
    notes.extend(risks)

    if risks:
        if consistency >= 35 and win_rate >= 55 and closed >= 20:
            return "RISKY", notes
        return "REJECT", notes

    if consistency >= 55 and win_rate >= 65 and closed >= 30 and worst > 0 and final_equity_units > 0:
        return "PROMISING", notes or ["balanced across files and risk metrics"]
    if consistency >= 35 and win_rate >= 55 and closed >= 20 and final_equity_units > 0:
        return "WATCHLIST", notes or ["usable but needs more validation"]
    return "REJECT", notes or ["metrics are not strong enough"]


def build_markdown_report(data: dict[str, Any], top: int) -> str:
    settings = data.get("settings") or {}
    rows = data.get("results") or []
    lines: list[str] = []
    lines.append("# Strategy Lab Report")
    lines.append("")
    lines.append("This report summarizes an offline portfolio sweep. It is an engineering decision aid, not a profitability guarantee.")
    lines.append("")
    lines.append("## Sweep settings")
    lines.append("")
    lines.append(f"- Files tested: {len(settings.get('files', []))}")
    lines.append(f"- Durations: {settings.get('durations', [])}")
    lines.append(f"- Candle seconds: {settings.get('candle_seconds', 'not recorded')}")
    lines.append(f"- Drop open candle: {settings.get('drop_open_candle', 'not recorded')}")
    lines.append(f"- Min confidences: {settings.get('min_confidences', [])}")
    lines.append(f"- Lookbacks: {settings.get('lookbacks', [])}")
    lines.append(f"- Steps: {settings.get('steps', [])}")
    lines.append("")
    lines.append("## Top candidates")
    lines.append("")
    lines.append("| Rank | Decision | Duration | Candle sec | Horizon | Min confidence | Lookback | Trades | Win rate | Loss rate | Max loss streak | Max DD | Final equity | Worst score | Consistency | Notes |")
    lines.append("|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|")

    for row in rows[:top]:
        decision, notes = classify_row(row)
        lines.append(
            "| "
            f"{row.get('rank', '')} | "
            f"{decision} | "
            f"{row.get('duration_seconds', '')} | "
            f"{row.get('candle_seconds', '')} | "
            f"{row.get('horizon_candles', '')} | "
            f"{row.get('min_confidence', '')} | "
            f"{row.get('lookback', '')} | "
            f"{row.get('closed_trades', '')} | "
            f"{float(row.get('win_rate_excluding_draws', 0) or 0):.2f}% | "
            f"{float(row.get('loss_rate', 0) or 0):.2f}% | "
            f"{row.get('max_consecutive_losses', '')} | "
            f"{row.get('max_drawdown_units', '')} | "
            f"{row.get('final_equity_units', '')} | "
            f"{float(row.get('worst_file_score', 0) or 0):.2f} | "
            f"{float(row.get('consistency_score', 0) or 0):.2f} | "
            f"{', '.join(notes)} |"
        )

    lines.append("")
    lines.append("## Recommended next action")
    lines.append("")
    if not rows:
        lines.append("No valid settings were found. Add more candle data or widen the sweep ranges.")
    else:
        best = rows[0]
        decision, notes = classify_row(best)
        if decision == "PROMISING":
            lines.append(
                "Keep the best candidate as a temporary benchmark, then validate it on fresh candle files before changing live demo behavior."
            )
        elif decision == "WATCHLIST":
            lines.append(
                "Do not promote this yet. Keep it on a watchlist and test more assets/time periods before changing the strategy defaults."
            )
        elif decision == "RISKY":
            lines.append(
                "Do not promote this candidate. Its headline metrics look usable, but the risk profile is too weak."
            )
        else:
            lines.append(
                "Do not change the strategy defaults from this sweep. The current candidate quality is not strong enough."
            )
        lines.append("")
        lines.append("Best candidate:")
        lines.append("")
        lines.append(f"- Duration: {best.get('duration_seconds')}")
        lines.append(f"- Candle seconds: {best.get('candle_seconds')}")
        lines.append(f"- Horizon candles: {best.get('horizon_candles')}")
        lines.append(f"- Drop open candle: {best.get('drop_open_candle')}")
        lines.append(f"- Min confidence: {best.get('min_confidence')}")
        lines.append(f"- Lookback: {best.get('lookback')}")
        lines.append(f"- Step: {best.get('step')}")
        lines.append(f"- Decision: {decision}")
        lines.append(f"- Notes: {', '.join(notes)}")

    lines.append("")
    lines.append("## Safety note")
    lines.append("")
    lines.append("This project remains DEMO-only. Backtest and sweep results do not justify real-money execution.")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a human-readable strategy lab report from a portfolio sweep JSON.")
    parser.add_argument("path", type=Path, help="Path to portfolio sweep JSON produced by sweep_portfolio.py")
    parser.add_argument("--top", type=int, default=10)
    parser.add_argument("--markdown-out", type=Path, help="Optional markdown report output path")
    args = parser.parse_args()

    data = load_portfolio_sweep(args.path)
    report = build_markdown_report(data, top=args.top)
    print(report)
    if args.markdown_out:
        args.markdown_out.write_text(report, encoding="utf-8")
        print(f"Markdown strategy lab report written: {args.markdown_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
