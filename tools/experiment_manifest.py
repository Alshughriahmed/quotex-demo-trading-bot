from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def repo_commit(root: Path) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return completed.stdout.strip() or None


def relative_or_absolute(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


def file_entry(path: Path, root: Path) -> dict[str, Any]:
    return {
        "path": relative_or_absolute(path, root),
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def build_manifest(
    *,
    root: Path,
    command: list[str],
    inputs: list[Path],
    outputs: list[Path],
    note: str,
) -> dict[str, Any]:
    missing_inputs = [str(path) for path in inputs if not path.exists()]
    missing_outputs = [str(path) for path in outputs if not path.exists()]
    if missing_inputs:
        raise FileNotFoundError(f"Input files not found: {missing_inputs}")
    if missing_outputs:
        raise FileNotFoundError(f"Output files not found: {missing_outputs}")

    return {
        "created_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "repo_commit": repo_commit(root),
        "command": command,
        "inputs": [file_entry(path, root) for path in inputs],
        "outputs": [file_entry(path, root) for path in outputs],
        "safety": {
            "demo_only": True,
            "note": note,
            "profitability_warning": "Backtest and sweep artifacts are engineering evidence only; they do not prove profitability or enable real-money trading.",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a reproducible manifest for offline strategy experiments.")
    parser.add_argument("--command", nargs="+", required=True, help="Command that produced the experiment artifacts")
    parser.add_argument("--input", action="append", type=Path, default=[], help="Input file used by the experiment; repeatable")
    parser.add_argument("--output", action="append", type=Path, default=[], help="Output artifact produced by the experiment; repeatable")
    parser.add_argument("--manifest-out", type=Path, required=True, help="Path to write the manifest JSON")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1], help="Repository root for relative paths and git commit lookup")
    parser.add_argument("--note", default="DEMO-only offline strategy experiment.")
    args = parser.parse_args()

    manifest = build_manifest(
        root=args.root,
        command=args.command,
        inputs=args.input,
        outputs=args.output,
        note=args.note,
    )
    args.manifest_out.parent.mkdir(parents=True, exist_ok=True)
    args.manifest_out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Experiment manifest written: {args.manifest_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
