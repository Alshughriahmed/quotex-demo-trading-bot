from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BOT_DIR = Path(__file__).resolve().parents[1]
INBOX_DIR = BOT_DIR / "external_inputs"
TEMPLATE_NAMES = {"replay_candles_template.csv"}
OUTPUT_PREFIX = "replay_ready_"
REQUIRED_OUTPUT = [
    "source_key",
    "asset",
    "timeframe_seconds",
    "candle_time",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "is_closed",
]

TIME_KEYS = {"time", "timestamp", "datetime", "date", "candle_time"}
OPEN_KEYS = {"open", "o"}
HIGH_KEYS = {"high", "h"}
LOW_KEYS = {"low", "l"}
CLOSE_KEYS = {"close", "c"}
VOLUME_KEYS = {"volume", "vol", "v"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert common OHLC CSV files into QTB replay candle CSV format.")
    parser.add_argument("input", nargs="?", help="Input CSV path. Defaults to newest non-template CSV in external_inputs.")
    parser.add_argument("--asset", required=True, help="Asset name to store, for example EUR/USD or USD/JPY.")
    parser.add_argument("--timeframe", type=int, default=60, help="Timeframe in seconds. Default: 60.")
    parser.add_argument("--source-key", default="converted_csv", help="Source key to store in replay CSV.")
    parser.add_argument("--output", help="Output CSV path. Default: replay_ready_<input-name>.csv in external_inputs.")
    parser.add_argument("--yes", action="store_true", help="Write output file. Without this flag, only dry-run summary is printed.")
    return parser.parse_args()


def is_template_or_output(path: Path) -> bool:
    name = path.name.lower()
    return name in TEMPLATE_NAMES or name.startswith(OUTPUT_PREFIX)


def resolve_input(raw: str | None) -> Path:
    if raw:
        path = Path(raw).expanduser()
        if not path.is_absolute():
            path = INBOX_DIR / path
    else:
        files = [path for path in INBOX_DIR.glob("*.csv") if not is_template_or_output(path)]
        files = sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)
        if not files:
            raise FileNotFoundError(f"No input CSV found in {INBOX_DIR}. Put a downloaded candle CSV there first.")
        path = files[0]
    path = path.resolve()
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(path)
    if path.suffix.lower() != ".csv":
        raise ValueError("Only CSV files are supported.")
    return path


def resolve_output(input_path: Path, raw: str | None) -> Path:
    if raw:
        path = Path(raw).expanduser()
        if not path.is_absolute():
            path = INBOX_DIR / path
    else:
        path = input_path.with_name(f"{OUTPUT_PREFIX}{input_path.stem}.csv")
    return path.resolve()


def sniff_dialect(sample: str) -> csv.Dialect:
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        return csv.excel


def normalize_key(key: str) -> str:
    return key.strip().lower().replace(" ", "_").replace(".", "_")


def looks_like_header(row: list[str]) -> bool:
    text = " ".join(cell.lower() for cell in row)
    return any(word in text for word in ("open", "high", "low", "close", "timestamp", "datetime", "date"))


def parse_time(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError("empty time")
    if text.endswith("Z"):
        return text
    candidates = [
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y.%m.%d %H:%M:%S",
        "%Y.%m.%d %H:%M",
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d %H:%M",
        "%Y%m%d %H%M%S",
        "%Y%m%d %H%M",
        "%Y%m%d%H%M%S",
        "%Y%m%d%H%M",
        "%Y-%m-%d",
        "%Y.%m.%d",
        "%Y/%m/%d",
    ]
    last_error: Exception | None = None
    for fmt in candidates:
        try:
            dt = datetime.strptime(text, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        except ValueError as exc:
            last_error = exc
    try:
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        raise ValueError(f"unsupported time format: {text}") from last_error


def clean_number(value: Any) -> str:
    text = str(value or "").strip().replace(",", ".")
    if not text:
        raise ValueError("empty number")
    float(text)
    return text


def pick(row: dict[str, str], keys: set[str]) -> str | None:
    for key, value in row.items():
        if normalize_key(key) in keys:
            return value
    return None


def convert_header_rows(rows: list[dict[str, str]], args: argparse.Namespace) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    for row in rows:
        time_value = pick(row, TIME_KEYS)
        if time_value is None and pick(row, {"date"}) and pick(row, {"time"}):
            time_value = f"{pick(row, {'date'})} {pick(row, {'time'})}"
        open_value = pick(row, OPEN_KEYS)
        high_value = pick(row, HIGH_KEYS)
        low_value = pick(row, LOW_KEYS)
        close_value = pick(row, CLOSE_KEYS)
        if None in (time_value, open_value, high_value, low_value, close_value):
            continue
        volume_value = pick(row, VOLUME_KEYS) or ""
        output.append(
            {
                "source_key": args.source_key,
                "asset": args.asset,
                "timeframe_seconds": str(args.timeframe),
                "candle_time": parse_time(str(time_value)),
                "open": clean_number(open_value),
                "high": clean_number(high_value),
                "low": clean_number(low_value),
                "close": clean_number(close_value),
                "volume": volume_value.strip() if isinstance(volume_value, str) else str(volume_value),
                "is_closed": "true",
            }
        )
    return output


def convert_plain_rows(rows: list[list[str]], args: argparse.Namespace) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    for row in rows:
        cells = [cell.strip() for cell in row]
        if len(cells) < 5:
            continue
        try:
            if len(cells) >= 7:
                time_value = f"{cells[0]} {cells[1]}"
                o, h, l, c = cells[2], cells[3], cells[4], cells[5]
                volume = cells[6] if len(cells) > 6 else ""
            else:
                time_value = cells[0]
                o, h, l, c = cells[1], cells[2], cells[3], cells[4]
                volume = cells[5] if len(cells) > 5 else ""
            output.append(
                {
                    "source_key": args.source_key,
                    "asset": args.asset,
                    "timeframe_seconds": str(args.timeframe),
                    "candle_time": parse_time(time_value),
                    "open": clean_number(o),
                    "high": clean_number(h),
                    "low": clean_number(l),
                    "close": clean_number(c),
                    "volume": volume,
                    "is_closed": "true",
                }
            )
        except ValueError:
            continue
    return output


def read_and_convert(path: Path, args: argparse.Namespace) -> list[dict[str, str]]:
    sample = path.read_text(encoding="utf-8-sig", errors="replace")[:4096]
    dialect = sniff_dialect(sample)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle, dialect)
        all_rows = [row for row in reader if any(cell.strip() for cell in row)]
    if not all_rows:
        return []
    if looks_like_header(all_rows[0]):
        headers = all_rows[0]
        dict_rows = [dict(zip(headers, row)) for row in all_rows[1:]]
        return convert_header_rows(dict_rows, args)
    return convert_plain_rows(all_rows, args)


def main() -> int:
    args = parse_args()
    input_path = resolve_input(args.input)
    output_path = resolve_output(input_path, args.output)

    print("=" * 72)
    print("QTB convert candle CSV to replay format")
    print("=" * 72)
    print("This converts a downloaded candle CSV into QTB replay CSV format.")
    print("It does not import data, does not start the bot, and does not trade.")
    print(f"Input: {input_path}")
    print(f"Output: {output_path}")
    print(f"Asset: {args.asset}")
    print(f"Timeframe seconds: {args.timeframe}")
    print(f"Source key: {args.source_key}")

    rows = read_and_convert(input_path, args)
    print(f"Converted rows: {len(rows)}")
    if rows:
        print(f"Period: {rows[0]['candle_time']} -> {rows[-1]['candle_time']}")
    if not rows:
        print("No convertible OHLC rows found. Check the CSV format.")
        return 1

    if not args.yes:
        print("Dry run only. Run again with --yes to write the replay-ready CSV.")
        print("=" * 72)
        return 0

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REQUIRED_OUTPUT)
        writer.writeheader()
        writer.writerows(rows)

    print("Replay-ready CSV written successfully.")
    print("Next: run replay_csv_inventory, then import_replay_candles dry-run.")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
