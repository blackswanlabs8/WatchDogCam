import os
from dataclasses import dataclass
from pathlib import Path


def _load_env_from_venv(env_path: Path = Path(".venv")) -> None:
    """Populate ``os.environ`` with values from a ``.venv`` file if it exists.

    The ``.venv`` file is expected to contain ``KEY=VALUE`` pairs, one per line.
    Lines starting with ``#`` or without an equals sign are ignored. Values are
    stripped of surrounding whitespace but otherwise left untouched.
    """

    if not env_path.exists() or not env_path.is_file():
        return

    with env_path.open() as file:
        for line in file:
            stripped = line.strip()

            if not stripped or stripped.startswith("#"):
                continue

            if "=" not in stripped:
                continue

            key, value = stripped.split("=", maxsplit=1)
            os.environ[key.strip()] = value.strip()


class SettingsError(Exception):
    """Raised when required settings are missing or invalid."""


@dataclass
class Settings:
    token: str
    chat_id: int
    cameras_file: Path
    check_interval_seconds: int = 300
    ping_timeout_seconds: int = 1


def load_settings() -> Settings:
    """Load settings from environment variables.

    Expected environment variables:
    - TELEGRAM_TOKEN: Telegram bot token (required)
    - TELEGRAM_CHAT_ID: chat id for notifications (required)
    - CAMERAS_FILE: path to cameras JSON file (default: cameras.json)
    - CHECK_INTERVAL_SECONDS: monitoring interval (default: 300)
    - PING_TIMEOUT_SECONDS: ping timeout (default: 1)
    """

    _load_env_from_venv()

    token = os.environ.get("TELEGRAM_TOKEN")
    chat_id_raw = os.environ.get("TELEGRAM_CHAT_ID")
    cameras_file_raw = os.environ.get("CAMERAS_FILE", "cameras.json")
    check_interval_raw = os.environ.get("CHECK_INTERVAL_SECONDS")
    ping_timeout_raw = os.environ.get("PING_TIMEOUT_SECONDS")

    if not token:
        raise SettingsError("TELEGRAM_TOKEN is not set")
    if not chat_id_raw:
        raise SettingsError("TELEGRAM_CHAT_ID is not set")

    try:
        chat_id = int(chat_id_raw)
    except ValueError as exc:
        raise SettingsError("TELEGRAM_CHAT_ID must be an integer") from exc

    check_interval_seconds = int(check_interval_raw) if check_interval_raw else 300
    ping_timeout_seconds = int(ping_timeout_raw) if ping_timeout_raw else 1

    return Settings(
        token=token,
        chat_id=chat_id,
        cameras_file=Path(cameras_file_raw),
        check_interval_seconds=check_interval_seconds,
        ping_timeout_seconds=ping_timeout_seconds,
    )
