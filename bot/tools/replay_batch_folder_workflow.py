from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

BOT_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BOT_DIR.parent
INBOX_DIR = BOT_DIR / "external_inputs"

MONTHLY_RAW_PATTERN = re.compile(r"^DAT_ASCII_([A-Z]{6})_M(\d+)_(20\d{4})\.csv$", re.IGNORECASE)
YEARLY_RAW_PATTERN = re.compile(r"^DAT_ASCII_([A-Z]{6})_M(\d+)_(20\d{2})\.csv$", re.IGNORECASE)

DEFAULT_ASSET_MAP = {
    "AUDCAD": "AUD/CAD",
    "AUDJPY": "AUD/JPY",
    "AUDNZD": "AUD/NZD",
    "AUDUSD": "AUD/USD",
    "CADJPY": "CAD/JPY",
    "CHFJPY": "CHF/JPY",
    "EURAUD": "EUR/AUD",
    "EURCAD": "EUR/CAD",
    "EURCHF": "EUR/CHF",
    "EURGBP": "EUR/GBP",
    "EURJPY": "EUR/JPY",
    "EURNZD": "EUR/NZD",
    "EURUSD": "EUR/USD",
    "GBPAUD": "GBP/AUD",
    "GBPCAD": "GBP/CAD",
    "GBPCHF": "GBP/CHF",
    "GBPJPY": "GBP/JPY",
    "GBPNZD": "GBP/NZD",
    "GBPUSD": "GBP/USD",
    "NZDCAD": "NZD/CAD",
    "NZDJPY": "NZD/JPY",
    "NZDUSD": "NZD/USD",
    "USDCAD": "USD/CAD",
    "USDCHF": "USD/CHF",
    "USDJPY": "USD/JPY",
}


@dataclass(frozen=True)
class RawFile:
    path: Path
    symbol: str
    asset: str
    period_raw: str
    period_kind: str
    timeframe_seconds: int
    source_key: str
    replay_filename: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Automated local replay research workflow for raw HistData CSV files in external_inputs.")
    parser.add_argument("--symbol", default="", help="Optional compact symbol filter, e.g. USDCAD or EURUSD.")
    parser.add_argument("--month", default="", help="Optional period filter, e.g. 202601, 2026-01, or yearly 2025.")
    parser.add_argument("--duration", type=int, default=60, help="Signal duration seconds. Default: 60.")
    parser.add_argument("--analysis-lookback", type=int, default=300, help="Trailing candle lookback. Default: 300.")
    parser.add_argument("--payout", type=float, default=0.80, help="Theoretical payout. Default: 0.80.")
    parser.add_argument("--limit-files", type=int, default=0, help="Optional max raw files to process, 0 means all.")
    parser.add_argument("--skip-reports", action="store_true", help="Skip final reports.")
    parser.add_argument("--yes", action="store_true", help="Actually run write steps. Without this flag, dry-run pipeline only.")
    return parser.parse_args()


def timeframe_from_m(minutes: int) -> int:
    return int(minutes) * 60


def compact_period(value: str) -> str:
    text = str(value or "").replace("-", "").strip()
    return text


def match_raw_file(path: Path) -> tuple[str, int, str, str] | None:
    monthly = MONTHLY_RAW_PATTERN.match(path.name)
    if monthly:
        return monthly.group(1).upper(), int(monthly.group(2)), monthly.group(3), "month"
    yearly = YEARLY_RAW_PATTERN.match(path.name)
    if yearly:
        return yearly.group(1).upper(), int(yearly.group(2)), yearly.group(3), "year"
    return None


def discover_files(symbol_filter: str, period_filter: str, limit_files: int) -> list[RawFile]:
    symbol_filter = symbol_filter.replace("/", "").upper().strip()
    period_filter = compact_period(period_filter)
    files: list[RawFile] = []
    seen_years: set[tuple[str, int, str]] = set()
    monthly_periods: set[tuple[str, int, str]] = set()

    raw_paths = sorted(INBOX_DIR.glob("DAT_ASCII_*_M*_20*.csv"))
    parsed: list[tuple[Path, str, int, str, str]] = []
    for path in raw_paths:
        matched = match_raw_file(path)
        if not matched:
            continue
        symbol, timeframe_minutes, period_raw, period_kind = matched
        if symbol_filter and symbol != symbol_filter:
            continue
        if period_filter:
            if period_filter != period_raw and not (len(period_filter) == 4 and period_raw.startswith(period_filter)):
                continue
        parsed.append((path, symbol, timeframe_minutes, period_raw, period_kind))
        if period_kind == "month":
            monthly_periods.add((symbol, timeframe_minutes, period_raw[:4]))

    for path, symbol, timeframe_minutes, period_raw, period_kind in parsed:
        year_key = (symbol, timeframe_minutes, period_raw[:4])
        if period_kind == "year" and year_key in monthly_periods:
            print(f"Skipping yearly file because monthly files for the same year already exist: {path.name}")
            continue
        if period_kind == "year":
            if year_key in seen_years:
                continue
            seen_years.add(year_key)
        asset = DEFAULT_ASSET_MAP.get(symbol, f"{symbol[:3]}/{symbol[3:]}")
        timeframe_seconds = timeframe_from_m(timeframe_minutes)
        source_key = f"histdata_{symbol.lower()}_m{timeframe_minutes}_{period_raw}"
        replay_filename = f"replay_ready_{path.stem}.csv"
        files.append(
            RawFile(
                path=path,
                symbol=symbol,
                asset=asset,
                period_raw=period_raw,
                period_kind=period_kind,
                timeframe_seconds=timeframe_seconds,
                source_key=source_key,
                replay_filename=replay_filename,
            )
        )
    if limit_files > 0:
        return files[:limit_files]
    return files


def run_command(args: list[str], *, label: str, allow_fail: bool = False) -> int:
    print("-" * 96)
    print(label)
    print("Command:", " ".join(args))
    print("-" * 96)
    completed = subprocess.run(args, cwd=str(BOT_DIR), text=True)
    if completed.returncode != 0 and not allow_fail:
        raise RuntimeError(f"Command failed with exit code {completed.returncode}: {label}")
    return int(completed.returncode)


def pytool(script: str, *args: str) -> list[str]:
    return [sys.executable, str(Path("tools") / script), *args]


def process_file(raw: RawFile, write: bool, duration: int, lookback: int, payout: float) -> None:
    strategy_version = f"replay_signal_only_v1_lookback_{lookback}"
    print("=" * 96)
    print(f"Processing {raw.path.name}")
    print(f"Asset: {raw.asset}")
    print(f"Period: {raw.period_raw} ({raw.period_kind})")
    print(f"Timeframe seconds: {raw.timeframe_seconds}")
    print(f"Source key: {raw.source_key}")
    print(f"Replay CSV: {raw.replay_filename}")
    print(f"Strategy version: {strategy_version}")
    print("=" * 96)

    convert_base = pytool(
        "convert_to_replay_candles.py",
        raw.path.name,
        "--asset",
        raw.asset,
        "--timeframe",
        str(raw.timeframe_seconds),
        "--source-key",
        raw.source_key,
        "--output",
        raw.replay_filename,
    )
    run_command(convert_base, label="Convert raw CSV dry-run")
    if write:
        run_command([*convert_base, "--yes"], label="Convert raw CSV write")

    if write:
        import_base = pytool("import_replay_candles.py", str(Path("external_inputs") / raw.replay_filename))
        run_command(import_base, label="Import replay candles dry-run")
        run_command([*import_base, "--yes"], label="Import replay candles write")

        reset_base = pytool(
            "replay_reset_research_for_source.py",
            "--source-key",
            raw.source_key,
            "--strategy-version",
            strategy_version,
            "--asset",
            raw.asset,
        )
        run_command(reset_base, label="Reset old matching research dry-run")
        run_command([*reset_base, "--yes"], label="Reset old matching research write")

        signals_base = pytool(
            "run_replay_signals.py",
            "--source-key",
            raw.source_key,
            "--asset",
            raw.asset,
            "--timeframe",
            str(raw.timeframe_seconds),
            "--duration",
            str(duration),
            "--analysis-lookback",
            str(lookback),
            "--progress-every",
            "10000",
        )
        run_command(signals_base, label="Run replay signals dry-run")
        run_command([*signals_base, "--yes"], label="Run replay signals write")

        outcomes_base = pytool(
            "evaluate_replay_outcomes.py",
            "--source-key",
            raw.source_key,
            "--asset",
            raw.asset,
            "--payout",
            f"{payout:.2f}",
        )
        run_command(outcomes_base, label="Evaluate replay outcomes dry-run")
        run_command([*outcomes_base, "--yes"], label="Evaluate replay outcomes write")


def main() -> int:
    args = parse_args()
    payout = max(0.0, min(1.0, float(args.payout)))
    duration = max(1, int(args.duration))
    lookback = max(0, int(args.analysis_lookback))
    write = bool(args.yes)

    print("=" * 96)
    print("QTB automated replay batch folder workflow")
    print("=" * 96)
    print("This runs locally over CSV files already in bot/external_inputs.")
    print("It supports monthly files like 202601 and yearly files like 2025.")
    print("If monthly files exist for a year, the matching yearly file is skipped to avoid duplicate periods.")
    print("It does not upload files, does not start the bot, does not connect to a broker, and does not trade.")
    print("It writes only research candles/signals/outcomes when --yes is used.")
    print(f"Inbox: {INBOX_DIR}")
    print(f"Mode: {'WRITE' if write else 'DRY-RUN ONLY'}")
    print(f"Symbol filter: {args.symbol.strip() or 'ALL'}")
    print(f"Period filter: {args.month.strip() or 'ALL'}")
    print(f"Duration: {duration}")
    print(f"Analysis lookback: {lookback}")
    print(f"Payout: {payout:.2f}")

    files = discover_files(args.symbol, args.month, max(0, int(args.limit_files)))
    if not files:
        print("No matching raw DAT_ASCII CSV files found.")
        return 1

    print("-" * 96)
    print(f"Raw files to process: {len(files)}")
    for raw in files:
        print(f"- {raw.path.name} -> {raw.asset} / {raw.source_key} / {raw.period_kind}")

    failures: list[str] = []
    for raw in files:
        try:
            process_file(raw, write, duration, lookback, payout)
        except Exception as exc:
            failures.append(f"{raw.path.name}: {exc}")
            print("!" * 96)
            print(f"FAILED: {raw.path.name}")
            print(exc)
            print("!" * 96)
            break

    print("=" * 96)
    print("Batch workflow summary")
    print("=" * 96)
    print(f"Requested files: {len(files)}")
    print(f"Failures: {len(failures)}")
    for failure in failures:
        print(f"- {failure}")

    if failures:
        print("Workflow stopped after first failure. Fix the issue and re-run.")
        return 1

    if write and not args.skip_reports:
        run_command(pytool("replay_csv_inventory.py"), label="Final replay CSV inventory")
        run_command(pytool("replay_multi_source_report.py"), label="Final multi-source report")
        run_command(
            pytool(
                "replay_counterfactual_report.py",
                "--payout",
                f"{payout:.2f}",
                "--min-trades",
                "100",
                "--top",
                "20",
            ),
            label="Final counterfactual report",
        )

    print("=" * 96)
    print("Replay batch folder workflow finished. No native trades were changed.")
    print("=" * 96)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
