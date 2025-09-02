import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand
from bot import router as bot_router
from admin import router as admin_router
from config import BOT_TOKEN, ADMIN_ID
from db import init_db, DB_PATH
import aiosqlite

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

async def clear_training_product():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT id, name FROM products WHERE name = 'Граббер телеграм'")
        product = await cursor.fetchone()
        if product:
            await db.execute("DELETE FROM products WHERE name = 'Граббер телеграм'")
            await db.commit()
            logger.info(f"Тренировочный товар '{product[1]}' (ID: {product[0]}) удалён")
        else:
            logger.info("Тренировочный товар не найден")

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
    
    await clear_training_product()  # Удаляем тренировочный товар
    
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