from __future__ import annotations

import runpy
from pathlib import Path
from typing import Any

import database
from trading.quotex_client import QuotexClient


BOT_DIR = Path(__file__).resolve().parent
MAIN_PATH = BOT_DIR / "main.py"
_original_buy_demo = QuotexClient.buy_demo


async def guarded_buy_demo(self: QuotexClient, *args: Any, **kwargs: Any) -> tuple[bool, dict[str, Any]]:
    setting = database.get_setting(self.db_path, "auto_buy_enabled", "false")
    if str(setting).lower() != "true":
        return False, {
            "error": "auto_buy_disabled",
            "message": "Automatic DEMO buying is disabled by local safety guard.",
        }
    return await _original_buy_demo(self, *args, **kwargs)


def install_runtime_guards() -> None:
    QuotexClient.buy_demo = guarded_buy_demo


def main() -> int:
    install_runtime_guards()
    print("Safe launcher active: auto-buy guard is enforced.")
    runpy.run_path(str(MAIN_PATH), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
