from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

BLOCKED_EXACT = {
    ".env",
    "bot/.env",
    "session.json",
    "bot/session.json",
    "data.db",
    "bot/data.db",
    "bot.log",
    "bot.pid",
}

BLOCKED_DIRS = {
    ".quotex",
    "bot/.quotex",
    "logs",
    "bot/logs",
    "backups",
    "bot/backups",
    "__pycache__",
}

BLOCKED_SUFFIXES = {
    ".db",
    ".db-journal",
    ".sqlite",
    ".sqlite3",
    ".pyc",
    ".pyo",
    ".log",
}

SUSPICIOUS_PATTERNS = [
    ("Telegram bot token", re.compile(r"\b\d{8,12}:[A-Za-z0-9_-]{25,}\b")),
    ("Possible password assignment", re.compile(r"(?i)\b(password|passwd|pwd)\s*=\s*[^\s#]+")),
    ("Possible API token assignment", re.compile(r"(?i)\b(token|api_key|apikey|secret)\s*=\s*[^\s#]+")),
]

TEXT_EXTENSIONS = {
    ".py",
    ".md",
    ".txt",
    ".example",
    ".yml",
    ".yaml",
    ".json",
    ".toml",
    ".ini",
    ".cfg",
    ".env",
    ".gitignore",
}

ALLOWLISTED_FILES = {
    ".env.example",
    "bot/.env.example",
    "tools/safety_check.py",
}


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def is_inside_blocked_dir(relative: str) -> bool:
    parts = relative.split("/")
    for index in range(len(parts)):
        candidate = "/".join(parts[: index + 1])
        if candidate in BLOCKED_DIRS or parts[index] in BLOCKED_DIRS:
            return True
    return False


def should_scan_text(path: Path) -> bool:
    if path.name == ".gitignore":
        return True
    return path.suffix.lower() in TEXT_EXTENSIONS or path.name.endswith(".example")


def check_blocked_paths() -> list[str]:
    problems: list[str] = []
    for path in ROOT.rglob("*"):
        if ".git" in path.parts:
            continue
        relative = rel(path)
        if relative in ALLOWLISTED_FILES:
            continue
        if relative in BLOCKED_EXACT:
            problems.append(f"Blocked sensitive path exists: {relative}")
            continue
        if path.is_dir() and is_inside_blocked_dir(relative):
            problems.append(f"Blocked runtime directory exists: {relative}/")
            continue
        if path.is_file() and path.suffix.lower() in BLOCKED_SUFFIXES:
            problems.append(f"Blocked runtime file exists: {relative}")
    return problems


def check_suspicious_text() -> list[str]:
    problems: list[str] = []
    for path in ROOT.rglob("*"):
        if ".git" in path.parts or not path.is_file():
            continue
        relative = rel(path)
        if relative in ALLOWLISTED_FILES:
            continue
        if not should_scan_text(path):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for label, pattern in SUSPICIOUS_PATTERNS:
            for match in pattern.finditer(text):
                line_number = text.count("\n", 0, match.start()) + 1
                problems.append(f"{label} in {relative}:{line_number}")
    return problems


def main() -> int:
    problems = []
    problems.extend(check_blocked_paths())
    problems.extend(check_suspicious_text())

    if problems:
        print("Safety check failed. Fix these before committing/pushing:\n")
        for problem in problems:
            print(f"- {problem}")
        return 1

    print("Safety check passed. No obvious secrets or runtime files found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
