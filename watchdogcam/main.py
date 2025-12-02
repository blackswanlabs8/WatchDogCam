import asyncio
import logging

from .config import SettingsError, load_settings
from .bot import run_bot

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    try:
        settings = load_settings()
    except SettingsError as exc:
        logger.error("Настройки недействительны: %s", exc)
        raise SystemExit(1) from exc

    asyncio.run(run_bot(settings))


if __name__ == "__main__":
    main()
