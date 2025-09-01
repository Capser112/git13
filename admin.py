from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from db import DB_PATH
import aiosqlite
from config import ADMIN_ID

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

@router.message(F.text == "Админ-панель")
async def admin_command(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Доступ запрещён.")
        return
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Добавить товар", callback_data="add_product")],
        [InlineKeyboardButton(text="Список товаров", callback_data="list_products")],
        [InlineKeyboardButton(text="Добавить промокод", callback_data="add_promocode")],
        [InlineKeyboardButton(text="Скидки", callback_data="discounts")],
        [InlineKeyboardButton(text="Статистика", callback_data="stats")],
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
        await db.execute(
            "INSERT INTO products (name, desc, price, category, subcategory, delivery_file) VALUES (?, ?, ?, ?, ?, ?)",
            (data["name"], data["desc"], data["price"], data["category"], data["subcategory"], None)
        )
        await db.commit()
    await message.answer("Товар добавлен!", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Назад", callback_data="back_to_admin")]
    ]))
    await state.clear()

@router.message(AdminStates.ADD_PRODUCT_FILE, F.document)
async def add_product_file(message: Message, state: FSMContext):
    data = await state.get_data()
    file_id = message.document.file_id
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO products (name, desc, price, category, subcategory, delivery_file) VALUES (?, ?, ?, ?, ?, ?)",
            (data["name"], data["desc"], data["price"], data["category"], data["subcategory"], file_id)
        )
        await db.commit()
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
        cursor = await db.execute("SELECT COUNT(*) FROM users")
        users_count = (await cursor.fetchone())[0]
        cursor = await db.execute("SELECT COUNT(*) FROM orders WHERE status = 'completed'")
        orders_count = (await cursor.fetchone())[0]
        cursor = await db.execute("SELECT SUM(amount) FROM orders WHERE status = 'completed'")
        total_revenue = (await cursor.fetchone())[0] or 0.0
    
    text = f"Статистика:\n\n" \
           f"Пользователей: {users_count}\n" \
           f"Завершённых заказов: {orders_count}\n" \
           f"Общая выручка: {total_revenue}$"
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Назад", callback_data="back_to_admin")]
    ]))

@router.callback_query(F.data == "back_to_admin")
async def back_to_admin(callback: CallbackQuery, state: FSMContext):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Добавить товар", callback_data="add_product")],
        [InlineKeyboardButton(text="Список товаров", callback_data="list_products")],
        [InlineKeyboardButton(text="Добавить промокод", callback_data="add_promocode")],
        [InlineKeyboardButton(text="Скидки", callback_data="discounts")],
        [InlineKeyboardButton(text="Статистика", callback_data="stats")],
        [InlineKeyboardButton(text="Назад", callback_data="back_to_main")]
    ])
    await callback.message.edit_text("Админ-панель:", reply_markup=kb)
    await state.set_state(AdminStates.MAIN)