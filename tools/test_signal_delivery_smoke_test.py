from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BOT_DIR = ROOT / "bot"
if str(BOT_DIR) not in sys.path:
    sys.path.insert(0, str(BOT_DIR))

from main import format_test_signal_failures, format_test_signal_result  # noqa: E402


def assert_contains(text: str, expected: str) -> None:
    if expected not in text:
        raise AssertionError(f"Expected {expected!r} in output:\n{text}")


def main() -> int:
    success_only = format_test_signal_result({"sent": [-100111], "failed": []})
    assert_contains(success_only, "تم إرسال إشارة تجريبية إلى 1 مجموعة.")

    partial = format_test_signal_result(
        {
            "sent": [-100111, -100222],
            "failed": [(-100333, "chat not found"), (-100444, "bot was kicked")],
        }
    )
    for expected in (
        "تم إرسال الإشارة التجريبية إلى 2 مجموعة.",
        "فشل الإرسال إلى 2 مجموعة.",
        "- -100333: chat not found",
        "- -100444: bot was kicked",
    ):
        assert_contains(partial, expected)

    all_failed = format_test_signal_failures(
        [(-100333, "chat not found"), (-100444, "bot was kicked")]
    )
    for expected in (
        "فشل إرسال الإشارة التجريبية لكل المجموعات.",
        "الأخطاء:",
        "- -100333: chat not found",
        "- -100444: bot was kicked",
    ):
        assert_contains(all_failed, expected)

    many_failed = format_test_signal_result(
        {
            "sent": [-100111],
            "failed": [(index, "error") for index in range(10)],
        }
    )
    assert_contains(many_failed, "... ومجموعات أخرى فاشلة: 5")

    print("Test signal delivery formatting smoke test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
