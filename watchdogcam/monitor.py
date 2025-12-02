import logging
from datetime import datetime, timezone
from typing import List

from telegram import Bot

from .config import Settings
from .ping import ping_host
from .storage import Camera, read_cameras, write_cameras

logger = logging.getLogger(__name__)


def _timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _human_time() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _status_message(camera: Camera) -> str | None:
    previous = camera.get("previous_status")
    current = camera.get("last_status")
    if previous == "online" and current == "offline":
        return (
            "⚠️ Камера перестала отвечать\n"
            f"Название: {camera.get('name')}\n"
            f"IP: {camera.get('ip')}\n"
            f"Время: {_human_time()}"
        )
    if previous == "offline" and current == "online":
        return (
            "✅ Камера снова в сети\n"
            f"Название: {camera.get('name')}\n"
            f"IP: {camera.get('ip')}\n"
            f"Время: {_human_time()}"
        )
    return None


def update_camera_status(camera: Camera, ping_timeout: int) -> Camera:
    if not camera.get("enabled", True):
        return camera

    new_status = "online" if ping_host(str(camera.get("ip")), timeout_seconds=ping_timeout) else "offline"

    previous_status = camera.get("last_status", "unknown")
    camera["previous_status"] = previous_status
    camera["last_status"] = new_status
    camera["last_check_at"] = _timestamp()

    if previous_status != new_status:
        camera["last_status_change_at"] = _timestamp()

    return camera


async def check_cameras(settings: Settings, bot: Bot) -> List[str]:
    cameras = read_cameras(settings.cameras_file)
    notifications: List[str] = []

    for camera in cameras:
        if not camera.get("enabled", True):
            continue
        update_camera_status(camera, settings.ping_timeout_seconds)
        msg = _status_message(camera)
        if msg:
            notifications.append(msg)

    write_cameras(settings.cameras_file, cameras)

    for note in notifications:
        try:
            await bot.send_message(chat_id=settings.chat_id, text=note)
        except Exception:  # Telegram errors should not stop monitoring
            logger.exception("Failed to send notification")

    return notifications
