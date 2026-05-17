from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]

FORBIDDEN_TRACKED_SUFFIXES = {
    ".db",
    ".sqlite",
    ".sqlite3",
    ".db-journal",
    ".log",
    ".zip",
    ".rar",
    ".7z",
    ".csv",
}

FORBIDDEN_TRACKED_NAMES = {
    ".env",
    "session.json",
    "bot.log",
    "bot.pid",
}

FORBIDDEN_TRACKED_PATH_PARTS = {
    "external_inputs",
    "extracted_external",
    "exports",
    "logs",
    "review_packages",
    ".quotex",
}

REQUIRED_GITIGNORE_ENTRIES = [
    ".env",
    "*.db",
    "*.sqlite",
    "*.sqlite3",
    "session.json",
    "bot/external_inputs/",
    "bot/extracted_external/",
    "bot/exports/",
    "*.zip",
    "*.csv",
]

# High-confidence secret patterns only. Do not flag normal variable names like token=... unless the value resembles a real secret.
SECRET_PATTERNS = [
    re.compile(r"(?i)bot[_-]?token\s*=\s*['\"]?\d{6,}:[A-Za-z0-9_-]{20,}"),
    re.compile(r"(?i)telegram[_-]?token\s*=\s*['\"]?\d{6,}:[A-Za-z0-9_-]{20,}"),
    re.compile(r"(?i)api[_-]?key\s*=\s*['\"][A-Za-z0-9_-]{24,}['\"]"),
    re.compile(r"(?i)secret[_-]?key\s*=\s*['\"][A-Za-z0-9_-]{24,}['\"]"),
]

TEXT_SUFFIXES = {".py", ".cmd", ".md", ".txt", ".toml", ".json", ".yml", ".yaml", ".gitignore"}


def run_git_ls_files() -> list[str]:
    completed = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT_DIR,
        text=True,
        capture_output=True,
        check=True,
    )
    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def check_tracked_paths(files: list[str]) -> list[str]:
    issues: list[str] = []
    for file_name in files:
        path = Path(file_name)
        parts = set(path.parts)
        lower_name = path.name.lower()
        lower_suffix = path.suffix.lower()

        if lower_name in FORBIDDEN_TRACKED_NAMES:
            issues.append(f"Tracked forbidden file name: {file_name}")
        if lower_suffix in FORBIDDEN_TRACKED_SUFFIXES:
            issues.append(f"Tracked forbidden file suffix: {file_name}")
        if parts.intersection(FORBIDDEN_TRACKED_PATH_PARTS):
            issues.append(f"Tracked forbidden local-data path: {file_name}")
    return issues


def check_gitignore() -> list[str]:
    gitignore = ROOT_DIR / ".gitignore"
    if not gitignore.exists():
        return ["Missing .gitignore"]
    text = read_text(gitignore)
    missing = [entry for entry in REQUIRED_GITIGNORE_ENTRIES if entry not in text]
    return [f"Missing .gitignore entry: {entry}" for entry in missing]


def check_secret_patterns(files: list[str]) -> list[str]:
    issues: list[str] = []
    for file_name in files:
        path = ROOT_DIR / file_name
        suffix = path.suffix.lower()
        if suffix and suffix not in TEXT_SUFFIXES:
            continue
        if path.name.lower() in FORBIDDEN_TRACKED_NAMES:
            continue
        try:
            text = read_text(path)
        except OSError:
            continue
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                issues.append(f"High-confidence secret-like value found in tracked file: {file_name}")
                break
    return issues


def main() -> int:
    print("=" * 72)
    print("QTB local safety check")
    print("=" * 72)
    print("This scans tracked project files only and does not print secret values.")

    try:
        tracked_files = run_git_ls_files()
    except Exception as exc:
        print(f"Could not list tracked files: {exc}")
        return 1

    issues: list[str] = []
    issues.extend(check_tracked_paths(tracked_files))
    issues.extend(check_gitignore())
    issues.extend(check_secret_patterns(tracked_files))

    print(f"Tracked files checked: {len(tracked_files)}")
    if issues:
        print("Result: FAILED")
        print("Issues:")
        for issue in issues:
            print(f"- {issue}")
        print("No secret values were printed.")
        print("=" * 72)
        return 1

    print("Result: PASSED")
    print("No tracked secrets, databases, logs, archives, exports, or external inputs were detected.")
    print("No secret values were printed.")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
