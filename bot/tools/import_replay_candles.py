from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


BOT_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BOT_DIR / "data.db"
INBOX_DIR = BOT_DIR / "external_inputs"
DEFAULT_SOURCE_KEY = "replay_csv"
TEMPLATE_FILENAMES = {"replay_candles_template.csv"}

import sys
if str(BOT_DIR) not in sys.path:
    sys.path.insert(0, str(BOT_DIR))

from market_sources import MarketCandle, validate_candle_sequence
from research import store_market_candles


REQUIRED_COLUMNS = {
    "asset",
    "timeframe_seconds",
    "candle_time",
    "open",
    "high",
    "low",
    "close",
}

OPTIONAL_COLUMNS = {"source_key", "volume", "is_closed"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import historical replay candles from CSV into research_market_candles.")
    parser.add_argument("archive", nargs="?", help="CSV file path. Defaults to newest non-template *.csv in bot/external_inputs.")
    parser.add_argument("--yes", action="store_true", help="Actually import. Without this flag, dry-run only.")
    parser.add_argument("--source-key", default=DEFAULT_SOURCE_KEY, help="Default source_key if CSV has no source_key column.")
    parser.add_argument("--limit", type=int, default=0, help="Optional maximum rows to read, 0 means all.")
    parser.add_argument("--allow-template", action="store_true", help="Allow importing the generated template CSV. For tests only.")
    return parser.parse_args()


def is_template_file(path: Path) -> bool:
    return path.name.lower() in TEMPLATE_FILENAMES


def resolve_csv(path_arg: str | None, allow_template: bool = False) -> Path:
    if path_arg:
        path = Path(path_arg)
        if not path.is_absolute():
            path = (Path.cwd() / path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"CSV file not found: {path}")
        if is_template_file(path) and not allow_template:
            raise ValueError(
                "Refusing to import replay_candles_template.csv. "
                "Copy it to a new filename and replace the sample rows with real historical candles."
            )
        return path

    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    all_files = sorted(INBOX_DIR.glob("*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
    files = [path for path in all_files if allow_template or not is_template_file(path)]
    if not files:
        if all_files:
            raise FileNotFoundError(
                f"Only template CSV files were found in {INBOX_DIR}. "
                "Copy replay_candles_template.csv to a new filename and replace the sample rows with real historical candles."
            )
        raise FileNotFoundError(f"No CSV files found in {INBOX_DIR}")
    return files[0]


def parse_bool(value: Any) -> bool:
    text = str(value or "").strip().lower()
    if text in {"", "1", "true", "yes", "y", "closed"}:
        return True
    if text in {"0", "false", "no", "n", "forming", "open"}:
        return False
    raise ValueError(f"invalid is_closed value: {value}")


def parse_time(value: str) -> datetime:
    text = str(value).strip()
    if not text:
        raise ValueError("candle_time is empty")
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def parse_float(row: dict[str, str], key: str) -> float:
    try:
        return float(str(row.get(key, "")).strip())
    except ValueError as exc:
        raise ValueError(f"invalid float for {key}: {row.get(key)!r}") from exc


def parse_int(row: dict[str, str], key: str) -> int:
    try:
        return int(float(str(row.get(key, "")).strip()))
    except ValueError as exc:
        raise ValueError(f"invalid integer for {key}: {row.get(key)!r}") from exc


def load_candles(csv_path: Path, default_source_key: str, limit: int = 0) -> list[MarketCandle]:
    candles: list[MarketCandle] = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        headers = set(reader.fieldnames or [])
        missing = sorted(REQUIRED_COLUMNS - headers)
        if missing:
            raise ValueError(f"CSV is missing required columns: {', '.join(missing)}")

        unknown = sorted(headers - REQUIRED_COLUMNS - OPTIONAL_COLUMNS)
        if unknown:
            print(f"Note: ignoring extra CSV columns: {', '.join(unknown)}")

        for index, row in enumerate(reader, start=1):
            if limit and len(candles) >= limit:
                break
            source_key = str(row.get("source_key") or default_source_key).strip()
            volume_text = str(row.get("volume") or "").strip()
            volume = None if volume_text == "" else float(volume_text)
            try:
                candles.append(
                    MarketCandle(
                        source_key=source_key,
                        asset=str(row.get("asset") or "").strip(),
                        timeframe_seconds=parse_int(row, "timeframe_seconds"),
                        candle_time=parse_time(str(row.get("candle_time") or "")),
                        open=parse_float(row, "open"),
                        high=parse_float(row, "high"),
                        low=parse_float(row, "low"),
                        close=parse_float(row, "close"),
                        volume=volume,
                        is_closed=parse_bool(row.get("is_closed", "true")),
                    )
                )
            except Exception as exc:
                raise ValueError(f"Row {index} is invalid: {exc}") from exc

    candles.sort(key=lambda c: (c.source_key, c.asset, c.timeframe_seconds, c.candle_time))
    return candles


def summarize(candles: list[MarketCandle]) -> None:
    print(f"Detected candles: {len(candles)}")
    if not candles:
        return
    sources = sorted({c.source_key for c in candles})
    assets = sorted({c.asset for c in candles})
    timeframes = sorted({c.timeframe_seconds for c in candles})
    print(f"Sources: {len(sources)} ({', '.join(sources[:8])})")
    print(f"Assets: {len(assets)} ({', '.join(assets[:12])})")
    print(f"Timeframes: {', '.join(str(tf) for tf in timeframes[:12])}")
    print(f"Period: {min(c.candle_time for c in candles).isoformat()} -> {max(c.candle_time for c in candles).isoformat()}")


def validate_by_group(candles: list[MarketCandle]) -> list[str]:
    issues: list[str] = []
    groups: dict[tuple[str, str, int], list[MarketCandle]] = {}
    for candle in candles:
        groups.setdefault((candle.source_key, candle.asset, candle.timeframe_seconds), []).append(candle)

    for key, group in groups.items():
        group_issues = validate_candle_sequence(group)
        if group_issues:
            source_key, asset, timeframe = key
            for issue in group_issues[:20]:
                issues.append(f"{source_key}/{asset}/{timeframe}: {issue}")
    return issues


def main() -> int:
    args = parse_args()
    print("=" * 72)
    print("QTB replay candle CSV importer")
    print("=" * 72)
    print("This imports historical candles into research_market_candles only.")
    print("It does not start the bot, does not connect to a broker, and does not trade.")

    try:
        csv_path = resolve_csv(args.archive, allow_template=args.allow_template)
        candles = load_candles(csv_path, args.source_key, max(0, args.limit))
        print(f"CSV: {csv_path}")
        summarize(candles)
        issues = validate_by_group(candles)
        if issues:
            print("Validation result: FAILED")
            for issue in issues[:50]:
                print(f"- {issue}")
            if len(issues) > 50:
                print(f"... plus {len(issues) - 50} more issues")
            return 1
        print("Validation result: PASSED")

        if not args.yes:
            print("Dry run only. Re-run with --yes to import.")
            return 0

        imported = 0
        groups: dict[tuple[str, str, int], list[MarketCandle]] = {}
        for candle in candles:
            groups.setdefault((candle.source_key, candle.asset, candle.timeframe_seconds), []).append(candle)
        for group in groups.values():
            imported += store_market_candles(DB_PATH, group)
        print(f"Imported/updated candles: {imported}")
        print("Replay candles are stored separately from native trades.")
    except Exception as exc:
        print(f"Import failed: {exc}")
        return 1

    print("=" * 72)
    print("Replay candle import finished. No secrets were printed and no native trades were changed.")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())