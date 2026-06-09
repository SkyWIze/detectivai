"""Точка входа. Запуск: python main.py"""
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from bot.handlers import routers
from config import config
from db import database

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("detective")


async def main() -> None:
    if not config.bot_token:
        raise SystemExit("BOT_TOKEN не задан. Скопируй .env.example в .env и заполни.")
    if not config.llm_enabled:
        log.warning("LLM_API_KEY пуст — бот работает на демо-деле (sample). Это нормально для отладки скелета.")

    await database.init_db()

    bot = Bot(token=config.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    for r in routers:
        dp.include_router(r)

    log.info("Detective bot запущен.")
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
