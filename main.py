import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.fsm.storage.memory import MemoryStorage
from config import BOT_TOKEN
from bot import register_handlers
from admin import register_admin_handlers
from db import init_db

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("logs/bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

async def main():
    logger.info("Starting bot...")
    
    # Инициализация бота и диспетчера
    bot = Bot(token=BOT_TOKEN, parse_mode="Markdown")
    dp = Dispatcher(storage=MemoryStorage())
    
    # Установка команд бота
    await bot.set_my_commands([
        types.BotCommand(command="/start", description="Запустить бота"),
        types.BotCommand(command="/catalog", description="Открыть каталог"),
        types.BotCommand(command="/profile", description="Посмотреть профиль"),
        types.BotCommand(command="/cart", description="Открыть корзину"),
        types.BotCommand(command="/help", description="Инструкция"),
        types.BotCommand(command="/admin", description="Админ-панель (для админа)")
    ])
    
    # Инициализация БД
    await init_db()
    
    # Регистрация хэндлеров
    register_handlers(dp)
    register_admin_handlers(dp)
    
    # Запуск polling
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())