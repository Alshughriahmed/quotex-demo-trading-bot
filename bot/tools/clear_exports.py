from __future__ import annotations

import argparse
from pathlib import Path


BOT_DIR = Path(__file__).resolve().parents[1]
EXPORT_DIR = BOT_DIR / "exports"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Delete local CSV exports from bot/exports.")
    parser.add_argument("--yes", action="store_true", help="Actually delete CSV files. Without this flag, only prints files.")
    return parser.parse_args()


def export_files() -> list[Path]:
    if not EXPORT_DIR.exists():
        return []
    return sorted(EXPORT_DIR.glob("*.csv"), key=lambda path: path.stat().st_mtime, reverse=True)


def main() -> int:
    args = parse_args()
    files = export_files()

    print(f"Export folder: {EXPORT_DIR}")
    print(f"CSV exports found: {len(files)}")

    if files:
        for path in files:
            print(f"- {path.name} ({path.stat().st_size} bytes)")

    if not args.yes:
        print("Dry run only. Add --yes to delete these local CSV exports.")
        return 0

    deleted = 0
    for path in files:
        path.unlink()
        deleted += 1

    print(f"Deleted CSV exports: {deleted}")
    print("Only local files under bot/exports were targeted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
