import asyncio
import logging
import uuid
from typing import List

from telegram import ReplyKeyboardMarkup, Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    ContextTypes,
    Job,
    filters,
)

from config import Settings
from monitor import check_cameras
from storage import (
    Camera,
    find_camera,
    read_cameras,
    read_subscribers,
    write_cameras,
    write_subscribers,
)

logger = logging.getLogger(__name__)

ADD_NAME, ADD_IP, DELETE_TARGET, EDIT_TARGET, EDIT_FIELD, EDIT_VALUE = range(6)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings: Settings = context.bot_data["settings"]
    chat_id = update.effective_chat.id if update.effective_chat else None

    text = (
        "Привет, я бот мониторинга камер.\n"
        "Я каждые 5 минут проверяю доступность камер и присылаю уведомления, если что-то меняется.\n\n"
        "Команды:\n"
        "• /all – все камеры и их статус\n"
        "• /online – только рабочие камеры\n"
        "• /offline – только нерабочие камеры\n"
        "• /stats – статистика\n"
        "• /refresh – обновить статусы камер\n"
        "• /add – добавить камеру\n"
        "• /edit – изменить камеру\n"
        "• /delete – удалить камеру"
    )
    if chat_id is not None:
        subscribers = read_subscribers(settings.subscribers_file)
        if chat_id not in subscribers:
            subscribers.append(chat_id)
            write_subscribers(settings.subscribers_file, subscribers)
            text += "\n\nВы подписаны на уведомления об изменении статуса камер."

    await update.message.reply_text(text)


def _format_camera_line(camera: Camera) -> str:
    status = camera.get("last_status", "unknown")
    if status == "online":
        status_text = "работает"
    elif status == "offline":
        status_text = "не работает"
    else:
        status_text = "неизвестно"
    return f"{camera.get('name')} – {camera.get('ip')} – {status_text}"


def _filter_cameras(cameras: List[Camera], status: str) -> List[Camera]:
    return [cam for cam in cameras if cam.get("last_status") == status and cam.get("enabled", True)]


async def list_all(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings: Settings = context.bot_data["settings"]
    cameras = read_cameras(settings.cameras_file)
    enabled_cameras = [c for c in cameras if c.get("enabled", True)]
    online = _filter_cameras(enabled_cameras, "online")
    offline = _filter_cameras(enabled_cameras, "offline")

    lines = [
        "📋 Все камеры",
        f"Всего: {len(enabled_cameras)}",
        f"Работают: {len(online)}",
        f"Не работают: {len(offline)}",
        "",
    ]
    lines.extend(_format_camera_line(cam) for cam in enabled_cameras)
    await update.message.reply_text("\n".join(lines))


async def list_online(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings: Settings = context.bot_data["settings"]
    cameras = read_cameras(settings.cameras_file)
    online = _filter_cameras(cameras, "online")

    if not online:
        await update.message.reply_text("Нет камер в статусе 'online'.")
        return

    lines = [f"✅ Рабочие камеры ({len(online)}):"]
    lines.extend(f"• {cam.get('name')} – {cam.get('ip')}" for cam in online)
    await update.message.reply_text("\n".join(lines))


async def list_offline(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings: Settings = context.bot_data["settings"]
    cameras = read_cameras(settings.cameras_file)
    offline = _filter_cameras(cameras, "offline")

    if not offline:
        await update.message.reply_text("✅ Все камеры в сети. Неработающих нет.")
        return

    lines = [f"⚠️ Неработающие камеры ({len(offline)}):"]
    lines.extend(f"• {cam.get('name')} – {cam.get('ip')}" for cam in offline)
    await update.message.reply_text("\n".join(lines))


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings: Settings = context.bot_data["settings"]
    cameras = read_cameras(settings.cameras_file)
    enabled_cameras = [c for c in cameras if c.get("enabled", True)]
    online = _filter_cameras(enabled_cameras, "online")
    offline = _filter_cameras(enabled_cameras, "offline")
    total = len(enabled_cameras)
    percent = round(len(online) / total * 100, 1) if total else 0

    text = (
        "📊 Статистика\n"
        f"Всего камер: {total}\n"
        f"Работают: {len(online)}\n"
        f"Не работают: {len(offline)}\n"
        f"Работает: {percent}%"
    )
    await update.message.reply_text(text)


async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Введите название камеры:")
    return ADD_NAME


async def add_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["new_camera_name"] = update.message.text.strip()
    await update.message.reply_text("Введите IP камеры:")
    return ADD_IP


async def add_ip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    settings: Settings = context.bot_data["settings"]
    ip = update.message.text.strip()
    name = context.user_data.pop("new_camera_name", "Камера")

    cameras = read_cameras(settings.cameras_file)
    new_camera = {
        "id": str(uuid.uuid4()),
        "name": name,
        "ip": ip,
        "enabled": True,
        "last_status": "unknown",
        "previous_status": "unknown",
        "last_check_at": None,
        "last_status_change_at": None,
    }
    cameras.append(new_camera)
    write_cameras(settings.cameras_file, cameras)

    await update.message.reply_text(
        "Камера добавлена:\n" f"Название: {name}\n" f"IP: {ip}"
    )
    return ConversationHandler.END


async def delete_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Введите IP или ID камеры для удаления:")
    return DELETE_TARGET


async def delete_target(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    settings: Settings = context.bot_data["settings"]
    target = update.message.text.strip()
    cameras = read_cameras(settings.cameras_file)
    camera = find_camera(cameras, target)

    if not camera:
        await update.message.reply_text("Камера не найдена. Попробуйте снова или отмените.")
        return ConversationHandler.END

    cameras = [c for c in cameras if c is not camera]
    write_cameras(settings.cameras_file, cameras)
    await update.message.reply_text(f"Камера {camera.get('name')} удалена.")
    return ConversationHandler.END


async def edit_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Введите IP или ID камеры для редактирования:")
    return EDIT_TARGET


async def edit_target(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    settings: Settings = context.bot_data["settings"]
    target = update.message.text.strip()
    cameras = read_cameras(settings.cameras_file)
    camera = find_camera(cameras, target)

    if not camera:
        await update.message.reply_text("Камера не найдена. Попробуйте снова или отмените.")
        return ConversationHandler.END

    context.user_data["edit_camera_id"] = camera.get("id")
    keyboard = ReplyKeyboardMarkup([["Название", "IP"]], one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(
        f"Редактируем {camera.get('name')} ({camera.get('ip')}). Что изменить?",
        reply_markup=keyboard,
    )
    return EDIT_FIELD


async def edit_field(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    choice = update.message.text.strip().lower()
    if choice not in {"название", "ip"}:
        await update.message.reply_text("Пожалуйста, выберите 'Название' или 'IP'.")
        return EDIT_FIELD

    context.user_data["edit_field"] = "name" if choice == "название" else "ip"
    await update.message.reply_text("Введите новое значение:")
    return EDIT_VALUE


async def edit_value(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    settings: Settings = context.bot_data["settings"]
    new_value = update.message.text.strip()
    field = context.user_data.get("edit_field")
    camera_id = context.user_data.get("edit_camera_id")

    if not field or not camera_id:
        await update.message.reply_text("Не удалось получить данные для редактирования.")
        return ConversationHandler.END

    cameras = read_cameras(settings.cameras_file)
    camera = find_camera(cameras, camera_id)
    if not camera:
        await update.message.reply_text("Камера не найдена.")
        return ConversationHandler.END

    camera[field] = new_value
    write_cameras(settings.cameras_file, cameras)
    await update.message.reply_text("Изменения сохранены.")
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Действие отменено.")
    return ConversationHandler.END


async def manual_check(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings: Settings = context.bot_data["settings"]
    bot = context.bot
    notifications = await check_cameras(settings, bot)
    message = "Проверка завершена."
    if notifications:
        message += "\n" + "\n".join(notifications)
    await update.message.reply_text(message)


async def refresh_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings: Settings = context.bot_data["settings"]
    bot = context.bot

    await check_cameras(settings, bot)
    cameras = read_cameras(settings.cameras_file)
    enabled_cameras = [c for c in cameras if c.get("enabled", True)]
    online = _filter_cameras(enabled_cameras, "online")
    offline = _filter_cameras(enabled_cameras, "offline")

    lines = [
        "🔄 Актуальные статусы камер",
        f"Проверено: {len(enabled_cameras)}",
        f"Работают: {len(online)}",
        f"Не работают: {len(offline)}",
    ]

    if offline:
        lines.append("")
        lines.append("⚠️ Неработающие камеры:")
        lines.extend(f"• {cam.get('name')} – {cam.get('ip')}" for cam in offline)

    if online:
        lines.append("")
        lines.append("✅ Работают:")
        lines.extend(f"• {cam.get('name')} – {cam.get('ip')}" for cam in online)

    await update.message.reply_text("\n".join(lines))


async def scheduled_check(context: ContextTypes.DEFAULT_TYPE) -> None:
    job = context.job
    if not job:
        logger.warning("Scheduled check called without job context")
        return

    settings: Settings = job.data["settings"]
    bot = job.application.bot
    await check_cameras(settings, bot)


def build_application(settings: Settings) -> Application:
    application = ApplicationBuilder().token(settings.token).build()
    application.bot_data["settings"] = settings

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("all", list_all))
    application.add_handler(CommandHandler("online", list_online))
    application.add_handler(CommandHandler("offline", list_offline))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("refresh", refresh_info))
    application.add_handler(CommandHandler("check", manual_check))

    add_handler = ConversationHandler(
        entry_points=[CommandHandler("add", add_start)],
        states={
            ADD_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_name)],
            ADD_IP: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_ip)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(add_handler)

    delete_handler = ConversationHandler(
        entry_points=[CommandHandler("delete", delete_start)],
        states={
            DELETE_TARGET: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_target)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(delete_handler)

    edit_handler = ConversationHandler(
        entry_points=[CommandHandler("edit", edit_start)],
        states={
            EDIT_TARGET: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_target)],
            EDIT_FIELD: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_field)],
            EDIT_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_value)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(edit_handler)

    application.job_queue.run_repeating(
        scheduled_check,
        interval=settings.check_interval_seconds,
        first=5,
        name="camera-monitor",
        data={"settings": settings},
    )

    return application


async def run_bot(settings: Settings) -> None:
    application = build_application(settings)
    await application.initialize()
    await application.start()
    logger.info("Bot started")

    try:
        await application.updater.start_polling()
        await asyncio.Event().wait()
    finally:
        await application.stop()
        await application.shutdown()
