from __future__ import annotations

import zipfile
from collections import Counter
from pathlib import Path


BOT_DIR = Path(__file__).resolve().parents[1]
INBOX_DIR = BOT_DIR / "external_inputs"
EXTRACT_DIR = BOT_DIR / "extracted_external"
ARCHIVE_SUFFIXES = {".zip", ".7z", ".rar"}
DATA_SUFFIXES = {".csv", ".db", ".sqlite", ".sqlite3", ".json", ".log", ".txt"}
SENSITIVE_MARKERS = (
    ".env",
    "token",
    "password",
    "passwd",
    "secret",
    "session",
    "cookie",
    "cookies",
    "credential",
    "credentials",
    "api_key",
    "apikey",
)


def is_sensitive_name(name: str) -> bool:
    lower = name.lower().replace("\\", "/")
    return any(marker in lower for marker in SENSITIVE_MARKERS)


def is_data_candidate(name: str) -> bool:
    return Path(name).suffix.lower() in DATA_SUFFIXES


def scan_zip(path: Path) -> dict:
    result = {
        "entries": 0,
        "data_candidates": [],
        "sensitive_candidates": [],
        "errors": [],
    }
    try:
        with zipfile.ZipFile(path) as archive:
            for info in archive.infolist():
                if info.is_dir():
                    continue
                result["entries"] += 1
                name = info.filename
                if is_data_candidate(name):
                    result["data_candidates"].append(name)
                if is_sensitive_name(name):
                    result["sensitive_candidates"].append(name)
    except Exception as exc:
        result["errors"].append(str(exc))
    return result


def main() -> int:
    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    EXTRACT_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 72)
    print("QTB external dataset inventory")
    print("=" * 72)
    print(f"Inbox: {INBOX_DIR}")
    print(f"Extraction folder: {EXTRACT_DIR}")
    print()

    files = [path for path in INBOX_DIR.rglob("*") if path.is_file()]
    if not files:
        print("No external files found yet.")
        print("Place an archive under bot\\external_inputs and run this again.")
        print("No secrets were printed.")
        return 0

    suffix_counts = Counter(path.suffix.lower() or "[no extension]" for path in files)
    print("Local files found:")
    for path in files:
        relative = path.relative_to(INBOX_DIR)
        marker = " ⚠️ sensitive-name" if is_sensitive_name(str(relative)) else ""
        print(f"- {relative} ({path.stat().st_size} bytes){marker}")

    print()
    print("File type summary:")
    for suffix, count in sorted(suffix_counts.items()):
        print(f"- {suffix}: {count}")

    archives = [path for path in files if path.suffix.lower() in ARCHIVE_SUFFIXES]
    print()
    print(f"Archives found: {len(archives)}")

    for archive_path in archives:
        relative = archive_path.relative_to(INBOX_DIR)
        print()
        print(f"Archive: {relative}")
        if archive_path.suffix.lower() != ".zip":
            print("- Content listing not supported yet for this archive type. Keep it local and review manually.")
            continue

        result = scan_zip(archive_path)
        if result["errors"]:
            print(f"- Could not inspect zip safely: {result['errors'][0]}")
            continue

        print(f"- Entries: {result['entries']}")
        print(f"- Data-like files: {len(result['data_candidates'])}")
        for name in result["data_candidates"][:20]:
            print(f"  data: {name}")
        if len(result["data_candidates"]) > 20:
            print(f"  ... {len(result['data_candidates']) - 20} more data-like files")

        print(f"- Sensitive-name candidates: {len(result['sensitive_candidates'])}")
        for name in result["sensitive_candidates"][:20]:
            print(f"  warning: {name}")
        if len(result["sensitive_candidates"]) > 20:
            print(f"  ... {len(result['sensitive_candidates']) - 20} more sensitive-name candidates")

    print()
    print("Result:")
    print("This was an inventory only. No archive was extracted and no file contents were printed.")
    print("Remove secrets before sharing or importing any external dataset.")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
