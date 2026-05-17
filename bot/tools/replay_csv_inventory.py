from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any


BOT_DIR = Path(__file__).resolve().parents[1]
INBOX_DIR = BOT_DIR / "external_inputs"
TEMPLATE_FILENAMES = {"replay_candles_template.csv"}
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
MONTH_PATTERN = re.compile(r"(20\d{4})")


def is_template_file(path: Path) -> bool:
    return path.name.lower() in TEMPLATE_FILENAMES


def month_from_text(value: str) -> str:
    match = MONTH_PATTERN.search(value or "")
    if not match:
        return ""
    raw = match.group(1)
    return f"{raw[:4]}-{raw[4:6]}"


def inspect_csv(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "name": path.name,
        "size": path.stat().st_size,
        "template": is_template_file(path),
        "rows": 0,
        "status": "UNKNOWN",
        "missing_columns": [],
        "extra_columns": [],
        "sources": set(),
        "assets": set(),
        "timeframes": set(),
        "first_time": "",
        "last_time": "",
        "warnings": [],
        "error": "",
    }
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            headers = set(reader.fieldnames or [])
            result["missing_columns"] = sorted(REQUIRED_COLUMNS - headers)
            result["extra_columns"] = sorted(headers - REQUIRED_COLUMNS - OPTIONAL_COLUMNS)
            if result["missing_columns"]:
                result["status"] = "INVALID_HEADERS"
                return result

            first_time = ""
            last_time = ""
            for row in reader:
                result["rows"] += 1
                source = str(row.get("source_key") or "").strip() or "(default)"
                asset = str(row.get("asset") or "").strip()
                timeframe = str(row.get("timeframe_seconds") or "").strip()
                candle_time = str(row.get("candle_time") or "").strip()
                if source:
                    result["sources"].add(source)
                if asset:
                    result["assets"].add(asset)
                if timeframe:
                    result["timeframes"].add(timeframe)
                if candle_time:
                    first_time = candle_time if not first_time else min(first_time, candle_time)
                    last_time = candle_time if not last_time else max(last_time, candle_time)
            result["first_time"] = first_time
            result["last_time"] = last_time
            if result["rows"] == 0:
                result["status"] = "EMPTY"
            elif result["template"]:
                result["status"] = "TEMPLATE_ONLY"
            else:
                result["status"] = "CANDIDATE"

            file_month = month_from_text(path.name)
            period_month = str(first_time or "")[:7]
            source_months = sorted({month_from_text(source) for source in result["sources"] if month_from_text(source)})
            if file_month and period_month and file_month != period_month:
                result["warnings"].append(f"filename month {file_month} does not match period month {period_month}")
            if period_month and source_months and any(source_month != period_month for source_month in source_months):
                result["warnings"].append(f"source_key month(s) {', '.join(source_months)} do not match period month {period_month}")
            if file_month and source_months and any(source_month != file_month for source_month in source_months):
                result["warnings"].append(f"source_key month(s) {', '.join(source_months)} do not match filename month {file_month}")
    except Exception as exc:
        result["status"] = "ERROR"
        result["error"] = str(exc)
    return result


def format_set(values: set[str], limit: int = 8) -> str:
    if not values:
        return ""
    ordered = sorted(values)
    text = ", ".join(ordered[:limit])
    if len(ordered) > limit:
        text += f", ... +{len(ordered) - limit}"
    return text


def main() -> int:
    print("=" * 72)
    print("QTB replay CSV inventory")
    print("=" * 72)
    print("This inspects CSV files in external_inputs only. It does not import data or trade.")
    print(f"Inbox: {INBOX_DIR}")

    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(INBOX_DIR.glob("*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        print("No CSV files found.")
        print("Put a real historical candle CSV in external_inputs before importing.")
        return 0

    print(f"CSV files found: {len(files)}")
    candidates = 0
    templates = 0
    invalid = 0
    warning_files = 0

    for path in files:
        info = inspect_csv(path)
        status = str(info["status"])
        if status == "CANDIDATE":
            candidates += 1
        elif status == "TEMPLATE_ONLY":
            templates += 1
        else:
            invalid += 1
        if info["warnings"]:
            warning_files += 1

        print("-" * 72)
        print(f"File: {info['name']}")
        print(f"Status: {status}")
        print(f"Size: {info['size']} bytes")
        print(f"Rows: {info['rows']}")
        if info["missing_columns"]:
            print(f"Missing required columns: {', '.join(info['missing_columns'])}")
        if info["extra_columns"]:
            print(f"Extra columns ignored by importer: {', '.join(info['extra_columns'])}")
        print(f"Sources: {format_set(info['sources'])}")
        print(f"Assets: {format_set(info['assets'])}")
        print(f"Timeframes: {format_set(info['timeframes'])}")
        print(f"Period: {info['first_time']} -> {info['last_time']}")
        for warning in info["warnings"]:
            print(f"WARNING: {warning}")
        if info["error"]:
            print(f"Error: {info['error']}")

    print("-" * 72)
    print("Decision")
    print("-" * 72)
    print(f"Import candidates: {candidates}")
    print(f"Templates only: {templates}")
    print(f"Invalid/error/empty files: {invalid}")
    print(f"Files with warnings: {warning_files}")
    if candidates == 0:
        print("No real replay CSV candidate found yet.")
        print("Do not run import_replay_candles until a real candle CSV exists.")
    elif warning_files:
        print("At least one candidate has warnings. Fix warnings before importing that file.")
    else:
        print("A candidate CSV exists. Run import_replay_candles first as dry-run and review the output before confirming import.")

    print("=" * 72)
    print("Replay CSV inventory finished. No files were imported and no native trades were changed.")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
