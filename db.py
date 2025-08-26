import aiosqlite
import logging

DB_PATH = "traffic_shop.db"

async def init_db():
    """Инициализация БД"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                ref_id INTEGER,
                balance REAL DEFAULT 0.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                desc TEXT,
                price REAL NOT NULL,
                category TEXT,
                delivery_file TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                product_id INTEGER,
                amount REAL,
                currency TEXT,
                status TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS referrals (
                user_id INTEGER,
                ref_user_id INTEGER,
                earnings REAL DEFAULT 0.0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS promocodes (
                code TEXT PRIMARY KEY,
                discount_percent INTEGER,
                expiration TIMESTAMP,
                max_uses INTEGER,
                uses_count INTEGER DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                user_id INTEGER,
                channel_id INTEGER,
                chat_id INTEGER,
                is_subscribed BOOLEAN DEFAULT FALSE
            )
        """)
        # Обновляем существующий товар
        await db.execute("""
            UPDATE products SET category = ? WHERE id = ?
        """, ("Обучения/Telegram", 1))
        # Тестовые товары
        await db.execute("""
            INSERT OR IGNORE INTO products (id, name, desc, price, category, delivery_file)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            1,
            "Auto-Motive1 | Связка по мотивированному трафику",
            "Бла бла бла. В комплекте софт:\n- Авто-обработка трафика\n- Авто-генерация трафика\nРезультат за месяц: *Фото*",
            60.0,
            "Обучения/Telegram",
            "link_to_file.zip"
        ))
        await db.execute("""
            INSERT OR IGNORE INTO products (name, desc, price, category, delivery_file)
            VALUES (?, ?, ?, ?, ?)
        """, (
            "TrafficGen | Генератор трафика",
            "Софт для автоматической генерации трафика в Telegram.\nОсобенности:\n- Настройка кампаний\n- Аналитика в реальном времени",
            45.0,
            "Софты/Telegram",
            "traffic_gen.zip"
        ))
        await db.commit()
        logging.info("Database initialized")


async def get_purchases_count(user_id: int) -> int:
    """Количество покупок юзера"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM orders WHERE user_id = ? AND status = ?", (user_id, "completed"))
        count = await cursor.fetchone()
        return count[0]

async def get_cart_items(user_id: int) -> list:
    """Получить товары в корзине (заглушка)"""
    return []  # Позже реализуем полноценную корзину

async def get_user(user_id: int) -> dict:
    """Получить данные юзера"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        user = await cursor.fetchone()
        if user:
            return {
                "id": user[0],
                "ref_id": user[1],
                "balance": user[2],
                "referrals_count": await get_referrals_count(user_id),
                "earnings": await get_referrals_earnings(user_id)
            }
        return None

async def add_user(user_id: int, ref_id: int = None):
    """Добавить юзера"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO users (id, ref_id) VALUES (?, ?)", (user_id, ref_id))
        await db.commit()

async def get_referrals_count(user_id: int) -> int:
    """Количество рефералов"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM referrals WHERE ref_user_id = ?", (user_id,))
        count = await cursor.fetchone()
        return count[0]

async def get_referrals_earnings(user_id: int) -> float:
    """Заработок от рефералов"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT SUM(earnings) FROM referrals WHERE ref_user_id = ?", (user_id,))
        earnings = await cursor.fetchone()
        return earnings[0] or 0.0