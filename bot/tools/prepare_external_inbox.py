from __future__ import annotations

from pathlib import Path


BOT_DIR = Path(__file__).resolve().parents[1]
INBOX_DIR = BOT_DIR / "external_inputs"
EXTRACT_DIR = BOT_DIR / "extracted_external"


def main() -> int:
    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    EXTRACT_DIR.mkdir(parents=True, exist_ok=True)

    readme = INBOX_DIR / "README.txt"
    if not readme.exists():
        readme.write_text(
            "Place external demo-bot archives here for local analysis only.\n"
            "Do not commit archives to Git. This folder is ignored by .gitignore.\n"
            "Remove .env files, tokens, session files, cookies, and passwords before sharing archives.\n",
            encoding="utf-8",
        )

    print(f"External inbox ready: {INBOX_DIR}")
    print(f"External extraction folder ready: {EXTRACT_DIR}")
    print("These folders are local-only and ignored by Git.")
    print("No files were imported yet.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
