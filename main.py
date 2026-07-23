import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import config
from database import requests as db
from database.db_main import init_db
from handlers import admin, client, common

logger = logging.getLogger(__name__)


async def check_reminders(bot: Bot) -> None:
    """Периодическая задача: находит записи в ближайшие 2 часа и шлёт клиентам напоминание."""
    bookings = await db.get_bookings_needing_reminder(hours_before=2)
    for booking in bookings:
        try:
            await bot.send_message(
                booking.user.telegram_id,
                "⏰ <b>Напоминание о записи!</b>\n\n"
                f"Совсем скоро жду тебя!:\n"
                f"💅 {booking.service.title}\n"
                f"📅 {booking.booking_date.strftime('%d.%m.%Y')} в {booking.booking_time}\n\n"
                "До встречи! 💅",
            )
            await db.mark_reminder_sent(booking.id)
        except Exception:
            logger.exception("Не удалось отправить напоминание пользователю %s", booking.user.telegram_id)


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Порядок важен: common должен ловить /start и кнопку "Отмена" для всех,
    # admin - обрабатывает только администраторов (фильтр внутри роутера),
    # client - обрабатывает сценарии обычных пользователей.
    dp.include_router(common.router)
    dp.include_router(admin.router)
    dp.include_router(client.router)

    await init_db()

    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_reminders, "interval", minutes=15, args=[bot])
    scheduler.start()

    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("Бот запущен и готов принимать сообщения.")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
