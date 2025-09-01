import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand
from aiogram.fsm.state import State, StatesGroup
from bot import router as bot_router
from admin import router as admin_router
from config import BOT_TOKEN, ADMIN_ID
from db import init_db
#from aiogram.types import DefaultBotProperties

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

async def set_commands(bot: Bot):
    """Установка команд бота"""
    commands = [
        BotCommand(command="/start", description="Начать"),
        BotCommand(command="/catalog", description="Каталог"),
        BotCommand(command="/profile", description="Профиль"),
        BotCommand(command="/cart", description="Корзина"),
        BotCommand(command="/help", description="Помощь"),

    ]
    await bot.set_my_commands(commands)

async def main():
    logger.info("Starting bot...")
    bot = Bot(token=BOT_TOKEN, parse_mode="Markdown")
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(bot_router)
    dp.include_router(admin_router)
    
    await init_db()
    await set_commands(bot)
    
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())