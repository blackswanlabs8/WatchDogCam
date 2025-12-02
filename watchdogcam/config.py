import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import find_dotenv, load_dotenv


def _load_env_from_venv(env_path: Path = Path(".venv")) -> None:
    """Populate ``os.environ`` with values from a ``.venv`` file if it exists.

    Uses ``python-dotenv`` for parsing so comments, blank lines, and quoted
    values are handled consistently with standard ``.env`` semantics.
    """

    load_dotenv(dotenv_path=env_path, override=True)


class SettingsError(Exception):
    """Raised when required settings are missing or invalid."""


def _load_env_from_dotenv(env_path: Path | None = None) -> None:
    """Populate ``os.environ`` with values from a ``.env`` file.

    The function prioritizes the `.env` file located next to ``main.py`` but
    will also search from the current working directory using ``find_dotenv``.
    If no file is found, a :class:`SettingsError` is raised with the inspected
    paths to help debug missing secrets.
    """

    primary_path = env_path or Path(__file__).resolve().parent / ".env"
    candidate_paths: list[Path] = [primary_path]

    discovered = find_dotenv(usecwd=True)
    if discovered:
        discovered_path = Path(discovered)
        if discovered_path not in candidate_paths:
            candidate_paths.append(discovered_path)

    for path in candidate_paths:
        if path.exists():
            load_dotenv(dotenv_path=path, override=True)
            return

    raise SettingsError(
        "Не найден файл .env с секретами. Проверьте наличие по путям: "
        + ", ".join(str(path) for path in candidate_paths)
    )


@dataclass
class Settings:
    token: str
    cameras_file: Path
    subscribers_file: Path
    check_interval_seconds: int = 300
    ping_timeout_seconds: int = 1


def load_settings() -> Settings:
    """Load settings from environment variables.

    Expected environment variables:
    - TELEGRAM_TOKEN: Telegram bot token (required)
    - CAMERAS_FILE: path to cameras JSON file (default: cameras.json)
    - SUBSCRIBERS_FILE: path to subscribers JSON file (default: subscribers.json)
    - CHECK_INTERVAL_SECONDS: monitoring interval (default: 300)
    - PING_TIMEOUT_SECONDS: ping timeout (default: 1)
    """

    _load_env_from_venv()
    _load_env_from_dotenv()

    token = os.environ.get("TELEGRAM_TOKEN")
    cameras_file_raw = os.environ.get("CAMERAS_FILE", "cameras.json")
    subscribers_file_raw = os.environ.get("SUBSCRIBERS_FILE", "subscribers.json")
    check_interval_raw = os.environ.get("CHECK_INTERVAL_SECONDS")
    ping_timeout_raw = os.environ.get("PING_TIMEOUT_SECONDS")

    if not token:
        raise SettingsError("TELEGRAM_TOKEN is not set")

    check_interval_seconds = int(check_interval_raw) if check_interval_raw else 300
    ping_timeout_seconds = int(ping_timeout_raw) if ping_timeout_raw else 1

    return Settings(
        token=token,
        cameras_file=Path(cameras_file_raw),
        subscribers_file=Path(subscribers_file_raw),
        check_interval_seconds=check_interval_seconds,
        ping_timeout_seconds=ping_timeout_seconds,
    )
