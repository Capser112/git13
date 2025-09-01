import aiosqlite
import logging
from datetime import datetime

DB_PATH = "traffic_shop.db"

async def init_db():
    """Инициализация БД"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                ref_id INTEGER,
                balance REAL DEFAULT 0.0,
                discount INTEGER DEFAULT 0,
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
                subcategory TEXT,
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
            CREATE TABLE IF NOT EXISTS cart (
                user_id INTEGER,
                product_id INTEGER,
                quantity INTEGER DEFAULT 1,
                PRIMARY KEY (user_id, product_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS invoices (
                invoice_id TEXT PRIMARY KEY,
                user_id INTEGER,
                product_id INTEGER,
                amount REAL,
                payload TEXT
            )
        """)
        # Тестовые товары с подкатегориями
        await db.execute("""
            INSERT OR IGNORE INTO products (id, name, desc, price, category, subcategory, delivery_file) VALUES
            (1, 'Граббер телеграм', 'Граббер для Telegram', 0.0, 'Бесплатное', 'Софты', 'file1.txt'),
            (2, 'Курс по арбитражу', 'Обучение арбитражу трафика', 20.0, 'Обучения и схемы', 'Курсы', 'file2.txt')
        """)
        await db.commit()

async def use_promocode(user_id: int, code: str) -> int:
    """Использовать промокод"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT discount_percent, uses_count, max_uses, expiration
            FROM promocodes WHERE code = ?
        """, (code,))
        promo = await cursor.fetchone()
        if promo and (promo[2] is None or promo[1] < promo[2]):
            discount, uses_count, max_uses, expiration = promo
            if expiration and datetime.strptime(expiration, "%Y-%m-%d %H:%M:%S") < datetime.now():
                return 0
            await db.execute("""
                UPDATE promocodes SET uses_count = uses_count + 1 WHERE code = ?
            """, (code,))
            await db.execute("""
                UPDATE users SET discount = ? WHERE id = ?
            """, (discount, user_id))
            await db.commit()
            return discount
        return 0

async def get_purchases_count(user_id: int) -> int:
    """Количество покупок юзера"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM orders WHERE user_id = ? AND status = ?", (user_id, "completed"))
        count = await cursor.fetchone()
        return count[0]

async def get_cart_items(user_id: int) -> list:
    """Получить товары в корзине"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT p.id, p.name, p.price 
            FROM cart c 
            JOIN products p ON c.product_id = p.id 
            WHERE c.user_id = ?
        """, (user_id,))
        return await cursor.fetchall()

async def get_user(user_id: int) -> dict:
    """Получить данные юзера"""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT id, ref_id, balance, discount FROM users WHERE id = ?", (user_id,))
        user = await cursor.fetchone()
        if user:
            return {
                "id": user[0],
                "ref_id": user[1],
                "balance": user[2],
                "discount": user[3] or 0,
                "referrals_count": await get_referrals_count(user_id),
                "earnings": await get_referrals_earnings(user_id)
            }
        return None

async def add_user(user_id: int, ref_id: int = None):
    """Добавить юзера"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO users (id, ref_id) VALUES (?, ?)", (user_id, ref_id))
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

async def remove_from_cart(user_id: int, product_id: int):
    """Удалить товар из корзины"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM cart WHERE user_id = ? AND product_id = ?", (user_id, product_id))
        await db.commit()