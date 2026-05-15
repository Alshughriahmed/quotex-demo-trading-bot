from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        input_path = tmp / "candles.json"
        output_path = tmp / "backtest.json"
        manifest_path = tmp / "manifest.json"
        input_path.write_text('{"candles": []}', encoding="utf-8")
        output_path.write_text('{"summary": {"closed_trades": 0}}', encoding="utf-8")

        completed = subprocess.run(
            [
                sys.executable,
                str(root / "tools" / "experiment_manifest.py"),
                "--command",
                "python",
                "tools/backtest_strategy.py",
                str(input_path),
                "--json-out",
                str(output_path),
                "--input",
                str(input_path),
                "--output",
                str(output_path),
                "--manifest-out",
                str(manifest_path),
                "--root",
                str(root),
                "--note",
                "DEMO-only smoke test experiment.",
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        if completed.returncode != 0:
            print(completed.stdout)
            print(completed.stderr, file=sys.stderr)
            return completed.returncode
        if not manifest_path.exists():
            raise AssertionError("Manifest file was not created")

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        required = ["created_at_utc", "repo_commit", "command", "inputs", "outputs", "safety"]
        missing = [key for key in required if key not in manifest]
        if missing:
            raise AssertionError(f"Manifest missing keys: {missing}")
        if manifest["command"][:2] != ["python", "tools/backtest_strategy.py"]:
            raise AssertionError(f"Unexpected command: {manifest['command']}")
        if len(manifest["inputs"]) != 1 or len(manifest["outputs"]) != 1:
            raise AssertionError("Manifest should contain exactly one input and one output")
        for section in ("inputs", "outputs"):
            entry = manifest[section][0]
            if not entry.get("sha256") or not entry.get("size_bytes"):
                raise AssertionError(f"Manifest {section} entry missing hash or size: {entry}")
        safety = manifest["safety"]
        if safety.get("demo_only") is not True:
            raise AssertionError("Manifest safety.demo_only must be true")
        if "does not prove profitability" not in safety.get("profitability_warning", ""):
            raise AssertionError("Manifest missing profitability warning")
        if "Experiment manifest written:" not in completed.stdout:
            raise AssertionError("Manifest tool did not print success output")

    print("Experiment manifest smoke test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
