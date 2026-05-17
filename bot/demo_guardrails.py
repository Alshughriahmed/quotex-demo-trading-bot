from __future__ import annotations

import sqlite3

import database


DEMO_ONLY_NOTICE = (
    "DEMO-only safety guardrail is active. "
    "REAL account selection and live-money execution are disabled in this development build."
)


def enforce_demo_only(db_path: str) -> None:
    """Force the bot into Telegram DEMO mode and hide unsafe stage controls."""
    database.set_setting(db_path, "account_type", "DEMO")
    with database.connect(db_path) as db:
        _disable_buttons(db)
        _relabel_buttons(db)
        _force_quotex_account_demo(db)
        db.commit()


def _disable_buttons(db: sqlite3.Connection) -> None:
    db.execute(
        """
        UPDATE telegram_admin_buttons
        SET enabled = 0,
            updated_at = CURRENT_TIMESTAMP
        WHERE button_key IN (
            'account_type_menu',
            'account_real',
            'quotex_menu',
            'change_quotex_email',
            'change_quotex_password',
            'add_admin'
        )
        """
    )


def _relabel_buttons(db: sqlite3.Connection) -> None:
    db.executemany(
        """
        UPDATE telegram_admin_buttons
        SET label = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE button_key = ?
        """,
        [
            ("▶️ تشغيل DEMO scanner إذا كان متوقف", "start_bot"),
            ("⏸️ إيقاف DEMO scanner إذا كان يعمل", "stop_bot"),
        ],
    )


def _force_quotex_account_demo(db: sqlite3.Connection) -> None:
    db.execute(
        """
        UPDATE quotex_accounts
        SET account_type = 'DEMO',
            enabled = 0,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = 1
        """
    )
