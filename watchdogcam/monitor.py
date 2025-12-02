import logging
from datetime import datetime, timezone
from typing import List

from telegram import Bot

from config import Settings
from ping import ping_host
from storage import Camera, read_cameras, read_subscribers, write_cameras

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

    ip = str(camera.get("ip"))
    name = camera.get("name", "Unknown")

    logger.info("Pinging camera %s (%s)", name, ip)
    is_online = ping_host(ip, timeout_seconds=ping_timeout)
    logger.info("Ping result for %s (%s): %s", name, ip, "online" if is_online else "offline")

    new_status = "online" if is_online else "offline"

    previous_status = camera.get("last_status", "unknown")
    camera["previous_status"] = previous_status
    camera["last_status"] = new_status
    camera["last_check_at"] = _timestamp()

    if previous_status != new_status:
        camera["last_status_change_at"] = _timestamp()

    return camera


async def check_cameras(settings: Settings, bot: Bot) -> List[str]:
    cameras = read_cameras(settings.cameras_file)
    subscribers = read_subscribers(settings.subscribers_file)
    notifications: List[str] = []

    for camera in cameras:
        if not camera.get("enabled", True):
            continue
        update_camera_status(camera, settings.ping_timeout_seconds)
        msg = _status_message(camera)
        if msg:
            notifications.append(msg)

    write_cameras(settings.cameras_file, cameras)

    unique_recipients = set(subscribers)

    for note in notifications:
        for recipient in unique_recipients:
            try:
                await bot.send_message(chat_id=recipient, text=note)
            except Exception:  # Telegram errors should not stop monitoring
                logger.exception("Failed to send notification")

    return notifications
