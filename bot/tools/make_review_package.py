from __future__ import annotations

import os
import zipfile
from datetime import datetime, timezone
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT_DIR / "review_packages"

EXCLUDE_DIR_NAMES = {
    ".git",
    ".github",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".venv",
    "venv",
    "env",
    "logs",
    "exports",
    "backups",
    "review_packages",
    "external_inputs",
    "extracted_external",
}

EXCLUDE_SUFFIXES = {
    ".db",
    ".sqlite",
    ".sqlite3",
    ".db-journal",
    ".log",
    ".zip",
    ".rar",
    ".7z",
    ".pyc",
    ".pyo",
    ".csv",
}

EXCLUDE_EXACT_NAMES = {
    ".env",
    "session.json",
    "bot.pid",
    "bot.log",
}

SENSITIVE_NAME_MARKERS = (
    "secret",
    "token",
    "password",
    "passwd",
    "credential",
    "credentials",
    "cookie",
    "cookies",
    "session",
    "api_key",
    "apikey",
)

INCLUDE_SUFFIXES = {
    ".py",
    ".cmd",
    ".md",
    ".txt",
    ".toml",
    ".json",
    ".yml",
    ".yaml",
    ".gitignore",
}

BRIEF = """# QTB External Review Brief

## Project goal

This project is a Quotex DEMO trading-bot research system. The current goal is not real-money trading. The goal is to build a safe, measurable, signal-first research pipeline.

## Current intended safety state

- REAL trading must remain disabled.
- Automatic DEMO buying must remain disabled by default.
- Scanner should stay stopped unless a safe market source is configured.
- Market source must be separated from order execution.
- External datasets must remain separate from native trades.
- Secrets must never be committed, printed, or included in review packages.

## What has already been built

- Safe launcher and guardrails.
- Local health check.
- Data quality report.
- External dataset inbox and inventory.
- External SQLite trade importer into external_* tables.
- Market source placeholder architecture.
- Documentation for signal-only market-source design.

## Important current state

- Native trades table is expected to be empty.
- External research data may contain imported historical DEMO trades.
- The project is not ready for real DEMO data collection until a market source is configured.
- Existing external dataset results are research-only and should not be treated as proof of profitability.

## Reviewer task

Please review the project deeply and provide concrete, evidence-based feedback.

Focus on:

1. Safety risks and possible ways execution could accidentally happen.
2. Separation between market data, strategy analysis, Telegram UI, database, and execution.
3. Database design and whether external_* tables are suitable for research.
4. Data quality reporting and whether it catches misleading states.
5. Strategy research workflow and how to improve analysis before any live DEMO execution.
6. Code quality, maintainability, and Windows .cmd usability.
7. Missing tests or validation checks.
8. Any design weakness that could distort win-rate/profit analysis.
9. Any security issue, especially secrets, tokens, sessions, cookies, logs, or local databases.
10. Specific next steps, ordered by priority.

Please avoid generic advice. For each finding, include:

- File/function involved.
- Why it matters.
- Risk level.
- How to fix it.
- What test or check should prove the fix works.

## Not requested yet

Do not suggest enabling REAL trading. Do not suggest bypassing broker protections. Do not suggest using credentials or sessions in unsafe ways. The current project should remain DEMO/signal-only until sufficient research data and guardrails exist.
"""


def is_excluded(path: Path) -> tuple[bool, str]:
    parts = set(path.parts)
    for part in parts:
        if part in EXCLUDE_DIR_NAMES:
            return True, f"excluded directory: {part}"

    name = path.name.lower()
    if name in EXCLUDE_EXACT_NAMES:
        return True, f"excluded exact name: {name}"

    suffix = path.suffix.lower()
    if suffix in EXCLUDE_SUFFIXES:
        return True, f"excluded suffix: {suffix}"

    lower_path = str(path).lower().replace(os.sep, "/")
    if any(marker in lower_path for marker in SENSITIVE_NAME_MARKERS):
        return True, "sensitive-looking filename"

    if suffix and suffix not in INCLUDE_SUFFIXES:
        return True, f"not an included source/document suffix: {suffix}"

    return False, "included"


def iter_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT_DIR.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(ROOT_DIR)
        excluded, _ = is_excluded(relative)
        if not excluded:
            files.append(path)
    return sorted(files)


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    zip_path = OUTPUT_DIR / f"qtb_review_package_{timestamp}.zip"

    files = iter_files()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("REVIEW_BRIEF.md", BRIEF)
        for path in files:
            relative = path.relative_to(ROOT_DIR)
            archive.write(path, relative.as_posix())

    print("=" * 72)
    print("QTB sanitized review package")
    print("=" * 72)
    print(f"Created: {zip_path}")
    print(f"Included files: {len(files) + 1}")
    print("Excluded secrets, databases, logs, exports, archives, and external inputs.")
    print("Safe to share for code/design review, but review the zip contents before sending.")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
