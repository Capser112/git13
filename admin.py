from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram import Bot
from db import DB_PATH
import aiosqlite
from config import ADMIN_ID
import logging
from datetime import datetime, timedelta

router = Router()

class AdminStates(StatesGroup):
    MAIN = State()
    ADD_PRODUCT_NAME = State()
    ADD_PRODUCT_DESC = State()
    ADD_PRODUCT_PRICE = State()
    ADD_PRODUCT_CATEGORY = State()
    ADD_PRODUCT_SUBCATEGORY = State()
    ADD_PRODUCT_FILE = State()
    ADD_PROMOCODE_CODE = State()
    ADD_PROMOCODE_DISCOUNT = State()
    ADD_PROMOCODE_MAX_USES = State()
    DELETE_PRODUCT = State()
    EDIT_PRODUCT = State()
    EDIT_PRODUCT_FIELD = State()
    BROADCAST_MESSAGE = State()
    MANAGE_CATEGORIES = State()
    ADD_CATEGORY = State()
    DELETE_CATEGORY = State()

@router.message(F.text == "Админ-панель")
async def admin_command(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Доступ запрещён.")
        return
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Добавить товар", callback_data="add_product")],
        [InlineKeyboardButton(text="Список товаров", callback_data="list_products")],
        [InlineKeyboardButton(text="Удалить товар", callback_data="delete_product")],
        [InlineKeyboardButton(text="Редактировать товар", callback_data="edit_product")],
        [InlineKeyboardButton(text="Управление категориями", callback_data="manage_categories")],
        [InlineKeyboardButton(text="Добавить промокод", callback_data="add_promocode")],
        [InlineKeyboardButton(text="Скидки", callback_data="discounts")],
        [InlineKeyboardButton(text="Статистика", callback_data="stats")],
        [InlineKeyboardButton(text="Рассылка", callback_data="broadcast")],
        [InlineKeyboardButton(text="Назад", callback_data="back_to_main")]
    ])
    await message.answer("Админ-панель:", reply_markup=kb)
    await state.set_state(AdminStates.MAIN)

@router.callback_query(F.data == "add_product", AdminStates.MAIN)
async def add_product_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Введите название товара:")
    await state.set_state(AdminStates.ADD_PRODUCT_NAME)

@router.message(AdminStates.ADD_PRODUCT_NAME)
async def add_product_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Введите описание товара:")
    await state.set_state(AdminStates.ADD_PRODUCT_DESC)

@router.message(AdminStates.ADD_PRODUCT_DESC)
async def add_product_desc(message: Message, state: FSMContext):
    await state.update_data(desc=message.text)
    await message.answer("Введите цену товара в $:")
    await state.set_state(AdminStates.ADD_PRODUCT_PRICE)

@router.message(AdminStates.ADD_PRODUCT_PRICE)
async def add_product_price(message: Message, state: FSMContext):
    try:
        price = float(message.text)
        if price < 0:
            raise ValueError
        await state.update_data(price=price)
        await message.answer("Введите категорию товара:")
        await state.set_state(AdminStates.ADD_PRODUCT_CATEGORY)
    except ValueError:
        await message.answer("Цена должна быть числом >= 0. Попробуй снова:")

@router.message(AdminStates.ADD_PRODUCT_CATEGORY)
async def add_product_category(message: Message, state: FSMContext):
    await state.update_data(category=message.text)
    await message.answer("Введите подкатегорию товара (или нажмите /skip для пропуска):")
    await state.set_state(AdminStates.ADD_PRODUCT_SUBCATEGORY)

@router.message(AdminStates.ADD_PRODUCT_SUBCATEGORY, F.text == "/skip")
async def skip_subcategory(message: Message, state: FSMContext):
    await state.update_data(subcategory=None)
    await message.answer("Отправьте файл товара (или нажмите /skip, если файла нет):")
    await state.set_state(AdminStates.ADD_PRODUCT_FILE)

@router.message(AdminStates.ADD_PRODUCT_SUBCATEGORY)
async def add_product_subcategory(message: Message, state: FSMContext):
    await state.update_data(subcategory=message.text)
    await message.answer("Отправьте файл товара (или нажмите /skip, если файла нет):")
    await state.set_state(AdminStates.ADD_PRODUCT_FILE)

@router.message(AdminStates.ADD_PRODUCT_FILE, F.text == "/skip")
async def skip_product_file(message: Message, state: FSMContext):
    data = await state.get_data()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM products WHERE name = ? AND desc = ? AND price = ? AND category = ? AND subcategory = ?",
            (data["name"], data["desc"], data["price"], data["category"], data["subcategory"])
        )
        if (await cursor.fetchone())[0] > 0:
            await message.answer("Такой товар уже существует!", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Назад", callback_data="back_to_admin")]
            ]))
            await state.clear()
            return
        await db.execute(
            "INSERT INTO products (name, desc, price, category, subcategory, delivery_file) VALUES (?, ?, ?, ?, ?, ?)",
            (data["name"], data["desc"], data["price"], data["category"], data["subcategory"], None)
        )
        await db.commit()
    logging.info(f"Product added: {data['name']} by user {message.from_user.id}")
    await message.answer("Товар добавлен!", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Назад", callback_data="back_to_admin")]
    ]))
    await state.clear()

@router.message(AdminStates.ADD_PRODUCT_FILE, F.document)
async def add_product_file(message: Message, state: FSMContext):
    data = await state.get_data()
    file_id = message.document.file_id
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM products WHERE name = ? AND desc = ? AND price = ? AND category = ? AND subcategory = ?",
            (data["name"], data["desc"], data["price"], data["category"], data["subcategory"])
        )
        if (await cursor.fetchone())[0] > 0:
            await message.answer("Такой товар уже существует!", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Назад", callback_data="back_to_admin")]
            ]))
            await state.clear()
            return
        await db.execute(
            "INSERT INTO products (name, desc, price, category, subcategory, delivery_file) VALUES (?, ?, ?, ?, ?, ?)",
            (data["name"], data["desc"], data["price"], data["category"], data["subcategory"], file_id)
        )
        await db.commit()
    logging.info(f"Product added with file: {data['name']} by user {message.from_user.id}")
    await message.answer("Товар добавлен!", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Назад", callback_data="back_to_admin")]
    ]))
    await state.clear()

@router.callback_query(F.data == "list_products", AdminStates.MAIN)
async def list_products(callback: CallbackQuery, state: FSMContext):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT id, name, price, category, subcategory FROM products")
        products = await cursor.fetchall()
    
    if not products:
        await callback.message.edit_text("Товаров нет.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Назад", callback_data="back_to_admin")]
        ]))
        return
    
    text = "Список товаров:\n\n"
    for product in products:
        product_id, name, price, category, subcategory = product
        text += f"ID: {product_id} | {name} | {price}$ | {category}{f' ({subcategory})' if subcategory else ''}\n"
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Назад", callback_data="back_to_admin")]
    ]))

@router.callback_query(F.data == "delete_product", AdminStates.MAIN)
async def delete_product_start(callback: CallbackQuery, state: FSMContext):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT id, name FROM products")
        products = await cursor.fetchall()
    
    if not products:
        await callback.message.edit_text("Товаров нет.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Назад", callback_data="back_to_admin")]
        ]))
        return
    
    kb_buttons = [[InlineKeyboardButton(text=f"{p[1]} (ID: {p[0]})", callback_data=f"delete_product_{p[0]}")] for p in products]
    kb_buttons.append([InlineKeyboardButton(text="Назад", callback_data="back_to_admin")])
    await callback.message.edit_text("Выберите товар для удаления:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_buttons))
    await state.set_state(AdminStates.DELETE_PRODUCT)

@router.callback_query(F.data.startswith("delete_product_"), AdminStates.DELETE_PRODUCT)
async def delete_product_confirm(callback: CallbackQuery, state: FSMContext):
    product_id = int(callback.data.split("_")[2])
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT name FROM products WHERE id = ?", (product_id,))
        product = await cursor.fetchone()
        if product:
            await db.execute("DELETE FROM products WHERE id = ?", (product_id,))
            await db.execute("DELETE FROM cart WHERE product_id = ?", (product_id,))
            await db.commit()
            logging.info(f"Product deleted: {product[0]} by user {callback.from_user.id}")
            await callback.message.edit_text(f"Товар {product[0]} удалён!", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Назад", callback_data="back_to_admin")]
            ]))
        else:
            await callback.message.edit_text("Товар не найден.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Назад", callback_data="back_to_admin")]
            ]))
    await state.set_state(AdminStates.MAIN)

@router.callback_query(F.data == "edit_product", AdminStates.MAIN)
async def edit_product_start(callback: CallbackQuery, state: FSMContext):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT id, name FROM products")
        products = await cursor.fetchall()
    
    if not products:
        await callback.message.edit_text("Товаров нет.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Назад", callback_data="back_to_admin")]
        ]))
        return
    
    kb_buttons = [[InlineKeyboardButton(text=f"{p[1]} (ID: {p[0]})", callback_data=f"edit_product_{p[0]}")] for p in products]
    kb_buttons.append([InlineKeyboardButton(text="Назад", callback_data="back_to_admin")])
    await callback.message.edit_text("Выберите товар для редактирования:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_buttons))
    await state.set_state(AdminStates.EDIT_PRODUCT)

@router.callback_query(F.data.startswith("edit_product_"), AdminStates.EDIT_PRODUCT)
async def edit_product_select_field(callback: CallbackQuery, state: FSMContext):
    product_id = int(callback.data.split("_")[2])
    await state.update_data(product_id=product_id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Название", callback_data="edit_field_name")],
        [InlineKeyboardButton(text="Описание", callback_data="edit_field_desc")],
        [InlineKeyboardButton(text="Цена", callback_data="edit_field_price")],
        [InlineKeyboardButton(text="Категория", callback_data="edit_field_category")],
        [InlineKeyboardButton(text="Подкатегория", callback_data="edit_field_subcategory")],
        [InlineKeyboardButton(text="Файл", callback_data="edit_field_file")],
        [InlineKeyboardButton(text="Назад", callback_data="back_to_admin")]
    ])
    await callback.message.edit_text("Выберите поле для редактирования:", reply_markup=kb)
    await state.set_state(AdminStates.EDIT_PRODUCT_FIELD)

@router.callback_query(F.data.startswith("edit_field_"), AdminStates.EDIT_PRODUCT_FIELD)
async def edit_product_field(callback: CallbackQuery, state: FSMContext):
    field = callback.data.split("_")[2]
    await state.update_data(field=field)
    if field == "file":
        await callback.message.edit_text("Отправьте новый файл (или /skip для удаления файла):")
    else:
        await callback.message.edit_text(f"Введите новое значение для {field}:")
    await state.set_state(AdminStates.EDIT_PRODUCT_FIELD)

@router.message(AdminStates.EDIT_PRODUCT_FIELD)
async def process_edit_field(message: Message, state: FSMContext):
    data = await state.get_data()
    product_id = data["product_id"]
    field = data["field"]
    value = message.text if field != "file" else (message.document.file_id if message.document else None)
    
    if field == "price":
        try:
            value = float(message.text)
            if value < 0:
                raise ValueError
        except ValueError:
            await message.answer("Цена должна быть числом >= 0. Попробуй снова:")
            return
    
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE products SET {field} = ? WHERE id = ?", (value, product_id))
        await db.commit()
    
    logging.info(f"Product {product_id} updated: {field} = {value} by user {message.from_user.id}")
    await message.answer(f"Поле {field} обновлено!", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Назад", callback_data="back_to_admin")]
    ]))
    await state.clear()

@router.message(AdminStates.EDIT_PRODUCT_FIELD, F.text == "/skip")
async def skip_edit_file(message: Message, state: FSMContext):
    data = await state.get_data()
    product_id = data["product_id"]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE products SET delivery_file = NULL WHERE id = ?", (product_id,))
        await db.commit()
    
    logging.info(f"Product {product_id} file removed by user {message.from_user.id}")
    await message.answer("Файл удалён!", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Назад", callback_data="back_to_admin")]
    ]))
    await state.clear()

@router.callback_query(F.data == "manage_categories", AdminStates.MAIN)
async def manage_categories(callback: CallbackQuery, state: FSMContext):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Добавить категорию", callback_data="add_category")],
        [InlineKeyboardButton(text="Удалить категорию", callback_data="delete_category")],
        [InlineKeyboardButton(text="Назад", callback_data="back_to_admin")]
    ])
    await callback.message.edit_text("Управление категориями:", reply_markup=kb)
    await state.set_state(AdminStates.MANAGE_CATEGORIES)

@router.callback_query(F.data == "add_category", AdminStates.MANAGE_CATEGORIES)
async def add_category_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Введите название новой категории:")
    await state.set_state(AdminStates.ADD_CATEGORY)

@router.message(AdminStates.ADD_CATEGORY)
async def process_add_category(message: Message, state: FSMContext):
    category = message.text
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM products WHERE category = ?", (category,))
        if (await cursor.fetchone())[0] > 0:
            await message.answer("Категория уже существует!", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Назад", callback_data="back_to_admin")]
            ]))
            await state.clear()
            return
    await message.answer(f"Категория {category} добавлена (используйте при добавлении товара).", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Назад", callback_data="back_to_admin")]
    ]))
    await state.clear()

@router.callback_query(F.data == "delete_category", AdminStates.MANAGE_CATEGORIES)
async def delete_category_start(callback: CallbackQuery, state: FSMContext):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT DISTINCT category FROM products")
        categories = [row[0] for row in await cursor.fetchall()]
    
    if not categories:
        await callback.message.edit_text("Категорий нет.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Назад", callback_data="back_to_admin")]
        ]))
        return
    
    kb_buttons = [[InlineKeyboardButton(text=cat, callback_data=f"delete_category_{cat}")] for cat in categories]
    kb_buttons.append([InlineKeyboardButton(text="Назад", callback_data="back_to_admin")])
    await callback.message.edit_text("Выберите категорию для удаления:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_buttons))
    await state.set_state(AdminStates.DELETE_CATEGORY)

@router.callback_query(F.data.startswith("delete_category_"), AdminStates.DELETE_CATEGORY)
async def delete_category_confirm(callback: CallbackQuery, state: FSMContext):
    category = callback.data.split("_")[2]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM products WHERE category = ?", (category,))
        await db.execute("DELETE FROM cart WHERE product_id IN (SELECT id FROM products WHERE category = ?)", (category,))
        await db.commit()
    logging.info(f"Category {category} deleted by user {callback.from_user.id}")
    await callback.message.edit_text(f"Категория {category} и все её товары удалены!", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Назад", callback_data="back_to_admin")]
    ]))
    await state.set_state(AdminStates.MAIN)

@router.callback_query(F.data == "broadcast", AdminStates.MAIN)
async def broadcast_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Введите сообщение для рассылки всем пользователям:")
    await state.set_state(AdminStates.BROADCAST_MESSAGE)

@router.message(AdminStates.BROADCAST_MESSAGE)
async def process_broadcast(message: Message, state: FSMContext, bot: Bot):
    text = message.text
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT id FROM users")
        users = [row[0] for row in await cursor.fetchall()]
    
    success_count = 0
    for user_id in users:
        try:
            await bot.send_message(user_id, text)
            success_count += 1
        except Exception as e:
            logging.error(f"Failed to send broadcast to {user_id}: {e}")
    
    logging.info(f"Broadcast sent to {success_count}/{len(users)} users by {message.from_user.id}")
    await message.answer(f"Рассылка отправлена {success_count}/{len(users)} пользователям!", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Назад", callback_data="back_to_admin")]
    ]))
    await state.clear()

@router.callback_query(F.data == "add_promocode", AdminStates.MAIN)
async def add_promocode_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Введите код промокода:")
    await state.set_state(AdminStates.ADD_PROMOCODE_CODE)

@router.message(AdminStates.ADD_PROMOCODE_CODE)
async def add_promocode_code(message: Message, state: FSMContext):
    await state.update_data(code=message.text)
    await message.answer("Введите процент скидки (0-100):")
    await state.set_state(AdminStates.ADD_PROMOCODE_DISCOUNT)

@router.message(AdminStates.ADD_PROMOCODE_DISCOUNT)
async def add_promocode_discount(message: Message, state: FSMContext):
    try:
        discount = int(message.text)
        if not 0 <= discount <= 100:
            raise ValueError
        await state.update_data(discount=discount)
        await message.answer("Введите максимальное количество использований (или /skip для бесконечного):")
        await state.set_state(AdminStates.ADD_PROMOCODE_MAX_USES)
    except ValueError:
        await message.answer("Процент должен быть числом от 0 до 100. Попробуй снова:")

@router.message(AdminStates.ADD_PROMOCODE_MAX_USES, F.text == "/skip")
async def skip_promocode_max_uses(message: Message, state: FSMContext):
    data = await state.get_data()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO promocodes (code, discount_percent, max_uses, uses_count) VALUES (?, ?, ?, ?)",
            (data["code"], data["discount"], None, 0)
        )
        await db.commit()
    await message.answer("Промокод добавлен!", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Назад", callback_data="back_to_admin")]
    ]))
    await state.clear()

@router.message(AdminStates.ADD_PROMOCODE_MAX_USES)
async def add_promocode_max_uses(message: Message, state: FSMContext):
    try:
        max_uses = int(message.text)
        if max_uses <= 0:
            raise ValueError
        data = await state.get_data()
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO promocodes (code, discount_percent, max_uses, uses_count) VALUES (?, ?, ?, ?)",
                (data["code"], data["discount"], max_uses, 0)
            )
            await db.commit()
        await message.answer("Промокод добавлен!", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Назад", callback_data="back_to_admin")]
        ]))
        await state.clear()
    except ValueError:
        await message.answer("Количество использований должно быть числом > 0. Попробуй снова:")

@router.callback_query(F.data == "discounts", AdminStates.MAIN)
async def discounts(callback: CallbackQuery, state: FSMContext):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT code, discount_percent, max_uses, uses_count FROM promocodes")
        promocodes = await cursor.fetchall()
    
    if not promocodes:
        await callback.message.edit_text("Промокодов нет.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Назад", callback_data="back_to_admin")]
        ]))
        return
    
    text = "Список промокодов:\n\n"
    for promo in promocodes:
        code, discount, max_uses, uses_count = promo
        text += f"Код: {code} | Скидка: {discount}% | Использовано: {uses_count}/{max_uses or '∞'}\n"
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Назад", callback_data="back_to_admin")]
    ]))

@router.callback_query(F.data == "stats", AdminStates.MAIN)
async def stats(callback: CallbackQuery, state: FSMContext):
    async with aiosqlite.connect(DB_PATH) as db:
        # Пользователи
        cursor = await db.execute("SELECT COUNT(*) FROM users")
        total_users = (await cursor.fetchone())[0]
        
        cursor = await db.execute("SELECT COUNT(*) FROM users WHERE created_at >= ?", (datetime.now() - timedelta(days=30),))
        users_month = (await cursor.fetchone())[0]
        
        cursor = await db.execute("SELECT COUNT(*) FROM users WHERE created_at >= ?", (datetime.now() - timedelta(days=7),))
        users_week = (await cursor.fetchone())[0]
        
        cursor = await db.execute("SELECT COUNT(*) FROM users WHERE created_at >= ?", (datetime.now() - timedelta(days=1),))
        users_yesterday = (await cursor.fetchone())[0]
        
        cursor = await db.execute("SELECT COUNT(*) FROM users WHERE created_at >= ?", (datetime.now().date(),))
        users_today = (await cursor.fetchone())[0]
        
        cursor = await db.execute("SELECT COUNT(*) FROM users WHERE created_at >= ?", (datetime.now() - timedelta(hours=1),))
        users_hour = (await cursor.fetchone())[0]
        
        # Заказы
        cursor = await db.execute("SELECT COUNT(*) FROM orders WHERE status = 'completed'")
        total_orders = (await cursor.fetchone())[0]
        
        cursor = await db.execute("SELECT COUNT(*) FROM orders WHERE status = 'completed' AND timestamp >= ?", (datetime.now() - timedelta(days=30),))
        orders_month = (await cursor.fetchone())[0]
        
        cursor = await db.execute("SELECT COUNT(*) FROM orders WHERE status = 'completed' AND timestamp >= ?", (datetime.now() - timedelta(days=7),))
        orders_week = (await cursor.fetchone())[0]
        
        cursor = await db.execute("SELECT COUNT(*) FROM orders WHERE status = 'completed' AND timestamp >= ?", (datetime.now() - timedelta(days=1),))
        orders_yesterday = (await cursor.fetchone())[0]
        
        cursor = await db.execute("SELECT COUNT(*) FROM orders WHERE status = 'completed' AND date(timestamp) = date('now')")
        orders_today = (await cursor.fetchone())[0]
        
        cursor = await db.execute("SELECT COUNT(*) FROM orders WHERE status = 'completed' AND timestamp >= ?", (datetime.now() - timedelta(hours=1),))
        orders_hour = (await cursor.fetchone())[0]
        
        cursor = await db.execute("SELECT SUM(amount) FROM orders WHERE status = 'completed'")
        total_revenue = (await cursor.fetchone())[0] or 0.0
        
        # Промокоды
        cursor = await db.execute("SELECT code, discount_percent, max_uses, uses_count FROM promocodes")
        promocodes = await cursor.fetchall()
    
    # Экранирование вне f-строк
    total_users_esc = str(total_users).replace('.', '\\.')
    users_month_esc = str(users_month).replace('.', '\\.')
    users_week_esc = str(users_week).replace('.', '\\.')
    users_yesterday_esc = str(users_yesterday).replace('.', '\\.')
    users_today_esc = str(users_today).replace('.', '\\.')
    users_hour_esc = str(users_hour).replace('.', '\\.')
    
    total_orders_esc = str(total_orders).replace('.', '\\.')
    orders_month_esc = str(orders_month).replace('.', '\\.')
    orders_week_esc = str(orders_week).replace('.', '\\.')
    orders_yesterday_esc = str(orders_yesterday).replace('.', '\\.')
    orders_today_esc = str(orders_today).replace('.', '\\.')
    orders_hour_esc = str(orders_hour).replace('.', '\\.')
    
    total_revenue_esc = str(total_revenue).replace('.', '\\.')
    
    # Формируем текст с экранированными значениями
    text = f"*Статистика*\n\n" \
           f"*Пользователи*\n" \
           f"Всего: {total_users_esc}\n" \
           f"За месяц: {users_month_esc}\n" \
           f"За неделю: {users_week_esc}\n" \
           f"Вчера: {users_yesterday_esc}\n" \
           f"Сегодня: {users_today_esc}\n" \
           f"За последний час: {users_hour_esc}\n\n" \
           f"*Заказы*\n" \
           f"Всего: {total_orders_esc}\n" \
           f"За месяц: {orders_month_esc}\n" \
           f"За неделю: {orders_week_esc}\n" \
           f"Вчера: {orders_yesterday_esc}\n" \
           f"Сегодня: {orders_today_esc}\n" \
           f"За последний час: {orders_hour_esc}\n\n" \
           f"*Выручка*\n" \
           f"Общая: {total_revenue_esc}$\n\n" \
           f"*Промокоды*\n"
    for promo in promocodes:
        code, discount, max_uses, uses_count = promo
        code_esc = code.replace('.', '\\.')
        discount_esc = str(discount).replace('.', '\\.')
        uses_count_esc = str(uses_count).replace('.', '\\.')
        max_uses_esc = str(max_uses).replace('.', '\\.') if max_uses else '∞'
        text += f"Код: {code_esc} | Скидка: {discount_esc}% | Активации: {uses_count_esc}/{max_uses_esc}\n"
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Назад", callback_data="back_to_admin")]
    ]), parse_mode="MarkdownV2")

@router.callback_query(F.data == "back_to_admin")
async def back_to_admin(callback: CallbackQuery, state: FSMContext):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Добавить товар", callback_data="add_product")],
        [InlineKeyboardButton(text="Список товаров", callback_data="list_products")],
        [InlineKeyboardButton(text="Удалить товар", callback_data="delete_product")],
        [InlineKeyboardButton(text="Редактировать товар", callback_data="edit_product")],
        [InlineKeyboardButton(text="Управление категориями", callback_data="manage_categories")],
        [InlineKeyboardButton(text="Добавить промокод", callback_data="add_promocode")],
        [InlineKeyboardButton(text="Скидки", callback_data="discounts")],
        [InlineKeyboardButton(text="Статистика", callback_data="stats")],
        [InlineKeyboardButton(text="Рассылка", callback_data="broadcast")],
        [InlineKeyboardButton(text="Назад", callback_data="back_to_main")]
    ])
    await callback.message.edit_text("Админ-панель:", reply_markup=kb)
    await state.set_state(AdminStates.MAIN)