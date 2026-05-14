from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


BOT_DIR = Path(__file__).resolve().parent
ENV_PATH = BOT_DIR / ".env"
PLACEHOLDER_VALUES = {
    "",
    "changeme",
    "change_me",
    "ضع_توكن_البوت_هنا",
    "put_your_bot_token_here",
}


class ConfigError(RuntimeError):
    """Raised when the local runtime configuration is missing or invalid."""


@dataclass(frozen=True)
class AppConfig:
    token: str
    db_path: str
    admin_ids: list[str]
    signals_chat_id: str
    env_path: Path

    def as_dict(self) -> dict:
        return {
            "token": self.token,
            "db_path": self.db_path,
            "admin_ids": self.admin_ids,
            "signals_chat_id": self.signals_chat_id,
            "env_path": str(self.env_path),
        }


def load_env(path: Path = ENV_PATH) -> dict[str, str]:
    values: dict[str, str] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")

    # Environment variables override .env values. This is useful on servers.
    return {**values, **os.environ}


def parse_csv(raw: str) -> list[str]:
    return [item.strip() for item in (raw or "").split(",") if item.strip()]


def validate_numeric_ids(name: str, values: list[str], *, allow_negative: bool = False) -> None:
    for value in values:
        candidate = value[1:] if allow_negative and value.startswith("-") else value
        if not candidate.isdigit():
            raise ConfigError(f"{name} contains an invalid id: {value}")


def require_not_placeholder(name: str, value: str) -> None:
    if value.strip().lower() in PLACEHOLDER_VALUES:
        raise ConfigError(f"{name} is missing or still uses a placeholder value.")


def normalize_db_path(raw: str) -> str:
    db_path = Path(raw.strip() or "data.db")
    if db_path.is_absolute():
        return str(db_path)
    return str(BOT_DIR / db_path)


def load_config(*, require_token: bool = True) -> AppConfig:
    env = load_env()

    token = env.get("TELEGRAM_BOT_TOKEN", "").strip()
    if require_token:
        require_not_placeholder("TELEGRAM_BOT_TOKEN", token)

    db_path = normalize_db_path(env.get("DATABASE_PATH", "data.db"))
    admin_ids = parse_csv(env.get("ADMIN_TELEGRAM_IDS", ""))
    signals_chat_id = env.get("SIGNALS_CHAT_ID", "").strip()

    if admin_ids:
        validate_numeric_ids("ADMIN_TELEGRAM_IDS", admin_ids)

    if signals_chat_id:
        validate_numeric_ids("SIGNALS_CHAT_ID", [signals_chat_id], allow_negative=True)

    return AppConfig(
        token=token,
        db_path=db_path,
        admin_ids=admin_ids,
        signals_chat_id=signals_chat_id,
        env_path=ENV_PATH,
    )


def startup_summary(config: AppConfig) -> str:
    admin_state = "configured" if config.admin_ids else "missing"
    signal_state = "configured" if config.signals_chat_id else "can be added later"
    token_state = "configured" if config.token else "missing"
    return (
        "Startup configuration:\n"
        f"- .env path: {config.env_path}\n"
        f"- Telegram token: {token_state}\n"
        f"- Admin IDs: {admin_state}\n"
        f"- Signals chat: {signal_state}\n"
        f"- Database path: {config.db_path}"
    )
