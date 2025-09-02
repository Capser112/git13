from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram import Bot
from db import DB_PATH, get_categories, add_category, delete_category
import aiosqlite
from config import ADMIN_ID
import logging
from datetime import datetime, timedelta
import asyncio
#from bot import send_message_with_retry

router = Router()

class AdminStates(StatesGroup):
    MAIN = State()
    ADD_PRODUCT_NAME = State()
    ADD_PRODUCT_DESC = State()
    ADD_PRODUCT_PRICE = State()
    ADD_PRODUCT_CATEGORY = State()
    ADD_PRODUCT_SUBCATEGORY = State()
    ADD_PRODUCT_MEDIA = State()
    ADD_PRODUCT_DELIVERY = State()
    ADD_PROMOCODE_CODE = State()
    ADD_PROMOCODE_DISCOUNT = State()
    ADD_PROMOCODE_MAX_USES = State()
    DELETE_PRODUCT = State()
    EDIT_PRODUCT = State()
    EDIT_PRODUCT_FIELD = State()
    BROADCAST_MESSAGE = State()
    MANAGE_CATEGORIES = State()
    ADD_CATEGORY_NAME = State()
    ADD_SUBCATEGORY_NAME = State()
    DELETE_CATEGORY = State()


async def edit_message_with_retry(message: Message, text: str, reply_markup=None, parse_mode=None, max_attempts=3):
    """Редактирование сообщения с повторными попытками"""
    for attempt in range(max_attempts):
        try:
            await message.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
            return True
        except Exception as e:
            logging.error(f"Failed to edit message: {e}, attempt {attempt + 1}/{max_attempts}")
            if attempt == max_attempts - 1:
                return False
            await asyncio.sleep(1)
    return False

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
    await send_message_with_retry(message.bot, message.chat.id, "Админ-панель:", reply_markup=kb)
    await state.set_state(AdminStates.MAIN)

@router.callback_query(F.data == "manage_categories", AdminStates.MAIN)
async def manage_categories(callback: CallbackQuery, state: FSMContext):
    categories = await get_categories()
    kb_buttons = [[InlineKeyboardButton(text=cat[1], callback_data=f"view_cat_{cat[0]}")] for cat in categories]
    kb_buttons.append([InlineKeyboardButton(text="Добавить категорию", callback_data="add_category")])
    kb_buttons.append([InlineKeyboardButton(text="Назад", callback_data="back_to_admin")])
    kb = InlineKeyboardMarkup(inline_keyboard=kb_buttons)
    await edit_message_with_retry(callback.message, "Категории:", reply_markup=kb)
    await state.set_state(AdminStates.MANAGE_CATEGORIES)

@router.callback_query(F.data == "add_category", AdminStates.MANAGE_CATEGORIES)
async def add_category_start(callback: CallbackQuery, state: FSMContext):
    await edit_message_with_retry(
        callback.message,
        "Введите название новой категории:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Назад", callback_data="manage_categories")]
        ])
    )
    await state.set_state(AdminStates.ADD_CATEGORY_NAME)

@router.message(AdminStates.ADD_CATEGORY_NAME)
async def add_category_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if await add_category(name):
        await send_message_with_retry(message.bot, message.chat.id, f"Категория '{name}' добавлена!")
    else:
        await send_message_with_retry(message.bot, message.chat.id, f"Категория '{name}' уже существует!")
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Управление категориями", callback_data="manage_categories")]
    ])
    await send_message_with_retry(message.bot, message.chat.id, "Админ-панель:", reply_markup=kb)
    await state.set_state(AdminStates.MAIN)

@router.callback_query(F.data.startswith("view_cat_"), AdminStates.MANAGE_CATEGORIES)
async def view_category(callback: CallbackQuery, state: FSMContext):
    category_id = int(callback.data.split("_")[2])
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT name FROM categories WHERE id = ?", (category_id,))
        category_name = (await cursor.fetchone())[0]
        subcategories = await get_categories(category_id)
    
    kb_buttons = [[InlineKeyboardButton(text=subcat[1], callback_data=f"view_subcat_{subcat[0]}")] for subcat in subcategories]
    kb_buttons.append([InlineKeyboardButton(text="Добавить подкатегорию", callback_data=f"add_subcategory_{category_id}")])
    kb_buttons.append([InlineKeyboardButton(text="Удалить категорию", callback_data=f"delete_category_{category_id}")])
    kb_buttons.append([InlineKeyboardButton(text="Назад", callback_data="manage_categories")])
    kb = InlineKeyboardMarkup(inline_keyboard=kb_buttons)
    await edit_message_with_retry(callback.message, f"Подкатегории в '{category_name}':", reply_markup=kb)

@router.callback_query(F.data.startswith("add_subcategory_"), AdminStates.MANAGE_CATEGORIES)
async def add_subcategory_start(callback: CallbackQuery, state: FSMContext):
    category_id = int(callback.data.split("_")[2])
    await state.update_data(category_id=category_id)
    await edit_message_with_retry(
        callback.message,
        "Введите название новой подкатегории:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Назад", callback_data="manage_categories")]
        ])
    )
    await state.set_state(AdminStates.ADD_SUBCATEGORY_NAME)

@router.message(AdminStates.ADD_SUBCATEGORY_NAME)
async def add_subcategory_name(message: Message, state: FSMContext):
    data = await state.get_data()
    category_id = data["category_id"]
    name = message.text.strip()
    if await add_category(name, category_id):
        await send_message_with_retry(message.bot, message.chat.id, f"Подкатегория '{name}' добавлена!")
    else:
        await send_message_with_retry(message.bot, message.chat.id, f"Подкатегория '{name}' уже существует!")
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Управление категориями", callback_data="manage_categories")]
    ])
    await send_message_with_retry(message.bot, message.chat.id, "Админ-панель:", reply_markup=kb)
    await state.set_state(AdminStates.MAIN)

@router.callback_query(F.data.startswith("delete_category_"), AdminStates.MANAGE_CATEGORIES)
async def delete_category_start(callback: CallbackQuery, state: FSMContext):
    category_id = int(callback.data.split("_")[2])
    if await delete_category(category_id):
        await edit_message_with_retry(
            callback.message,
            "Категория удалена!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Управление категориями", callback_data="manage_categories")]
            ])
        )
    else:
        await edit_message_with_retry(
            callback.message,
            "Нельзя удалить категорию, так как в ней есть товары.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Управление категориями", callback_data="manage_categories")]
            ])
        )
    await state.set_state(AdminStates.MANAGE_CATEGORIES)

@router.callback_query(F.data == "add_product", AdminStates.MAIN)
async def add_product_start(callback: CallbackQuery, state: FSMContext):
    await edit_message_with_retry(
        callback.message,
        "Введите название товара:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Назад", callback_data="back_to_admin")]
        ])
    )
    await state.set_state(AdminStates.ADD_PRODUCT_NAME)

@router.message(AdminStates.ADD_PRODUCT_NAME)
async def add_product_name(message: Message, state: FSMContext):
    if message.text == "/skip":
        await send_message_with_retry(message.bot, message.chat.id, "Название товара обязательно. Введите название:")
        return
    
    await state.update_data(name=message.text)
    await send_message_with_retry(
        message.bot,
        message.chat.id,
        "Введите описание товара (или /skip, чтобы пропустить):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Назад", callback_data="add_product")]
        ])
    )
    await state.set_state(AdminStates.ADD_PRODUCT_DESC)

@router.message(AdminStates.ADD_PRODUCT_DESC)
async def add_product_desc(message: Message, state: FSMContext):
    if message.text == "/skip":
        await state.update_data(desc=None)
    else:
        await state.update_data(desc=message.text)
    
    await send_message_with_retry(
        message.bot,
        message.chat.id,
        "Введите цену товара в $ (0 для бесплатных):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Назад", callback_data="add_product_name")]
        ])
    )
    await state.set_state(AdminStates.ADD_PRODUCT_PRICE)

@router.message(AdminStates.ADD_PRODUCT_PRICE)
async def add_product_price(message: Message, state: FSMContext):
    try:
        price = float(message.text)
        if price < 0:
            await send_message_with_retry(
                message.bot,
                message.chat.id,
                "Цена не может быть отрицательной. Введите цену заново:",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Назад", callback_data="add_product_desc")]
                ])
            )
            return
        await state.update_data(price=price)
        categories = await get_categories()
        if not categories:
            await send_message_with_retry(
                message.bot,
                message.chat.id,
                "Нет категорий. Создайте категорию в 'Управление категориями'.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Назад", callback_data="back_to_admin")]
                ])
            )
            await state.clear()
            return
        kb_buttons = [[InlineKeyboardButton(text=cat[1], callback_data=f"cat_{cat[0]}")] for cat in categories]
        kb_buttons.append([InlineKeyboardButton(text="Назад", callback_data="add_product_price")])
        kb = InlineKeyboardMarkup(inline_keyboard=kb_buttons)
        await send_message_with_retry(message.bot, message.chat.id, "Выберите категорию товара:", reply_markup=kb)
        await state.set_state(AdminStates.ADD_PRODUCT_CATEGORY)
    except ValueError:
        await send_message_with_retry(
            message.bot,
            message.chat.id,
            "Цена должна быть числом >= 0. Попробуй снова:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Назад", callback_data="add_product_desc")]
            ])
        )

@router.callback_query(F.data.startswith("cat_"), AdminStates.ADD_PRODUCT_CATEGORY)
async def add_product_category(callback: CallbackQuery, state: FSMContext):
    category_id = int(callback.data.split("_")[1])
    await state.update_data(category_id=category_id)
    subcategories = await get_categories(category_id)
    kb_buttons = [[InlineKeyboardButton(text="Без подкатегории", callback_data="no_subcategory")]]
    kb_buttons.extend([[InlineKeyboardButton(text=subcat[1], callback_data=f"subcat_{subcat[0]}")] for subcat in subcategories])
    kb_buttons.append([InlineKeyboardButton(text="Назад", callback_data="add_product_price")])
    kb = InlineKeyboardMarkup(inline_keyboard=kb_buttons)
    await edit_message_with_retry(callback.message, "Выберите подкатегорию (или 'Без подкатегории'):", reply_markup=kb)
    await state.set_state(AdminStates.ADD_PRODUCT_SUBCATEGORY)

@router.callback_query(F.data == "no_subcategory", AdminStates.ADD_PRODUCT_SUBCATEGORY)
async def skip_subcategory(callback: CallbackQuery, state: FSMContext):
    await state.update_data(subcategory_id=None)
    await edit_message_with_retry(
        callback.message,
        "Отправьте фото или гиф для карточки товара (или /skip, чтобы пропустить):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Назад", callback_data="add_product_category")]
        ])
    )
    await state.set_state(AdminStates.ADD_PRODUCT_MEDIA)

@router.callback_query(F.data.startswith("subcat_"), AdminStates.ADD_PRODUCT_SUBCATEGORY)
async def add_product_subcategory(callback: CallbackQuery, state: FSMContext):
    subcategory_id = int(callback.data.split("_")[1])
    await state.update_data(subcategory_id=subcategory_id)
    await edit_message_with_retry(
        callback.message,
        "Отправьте фото или гиф для карточки товара (или /skip, чтобы пропустить):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Назад", callback_data="add_product_category")]
        ])
    )
    await state.set_state(AdminStates.ADD_PRODUCT_MEDIA)

@router.message(AdminStates.ADD_PRODUCT_MEDIA)
async def add_product_media(message: Message, state: FSMContext):
    if message.text == "/skip":
        await state.update_data(media=None)
    elif message.photo:
        await state.update_data(media=message.photo[-1].file_id)
    elif message.animation:
        await state.update_data(media=message.animation.file_id)
    else:
        await send_message_with_retry(
            message.bot,
            message.chat.id,
            "Отправьте фото или гиф (или /skip, чтобы пропустить):",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Назад", callback_data="add_product_subcategory")]
            ])
        )
        return
    
    await send_message_with_retry(
        message.bot,
        message.chat.id,
        "Отправьте текст инструкции, ссылку, фото, гиф или файл для доставки покупателю (или /skip, чтобы пропустить):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Назад", callback_data="add_product_media")]
        ])
    )
    await state.set_state(AdminStates.ADD_PRODUCT_DELIVERY)

@router.message(AdminStates.ADD_PRODUCT_DELIVERY)
async def add_product_delivery(message: Message, state: FSMContext):
    data = await state.get_data()
    if message.text == "/skip":
        delivery_file = None
    elif message.text:
        delivery_file = message.text
    elif message.photo:
        delivery_file = message.photo[-1].file_id
    elif message.animation:
        delivery_file = message.animation.file_id
    elif message.document:
        delivery_file = message.document.file_id
    else:
        await send_message_with_retry(
            message.bot,
            message.chat.id,
            "Отправьте текст, фото, гиф или файл (или /skip, чтобы пропустить):",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Назад", callback_data="add_product_media")]
            ])
        )
        return
    
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM products WHERE name = ? AND category_id = ? AND subcategory_id = ?",
            (data["name"], data["category_id"], data.get("subcategory_id"))
        )
        if (await cursor.fetchone())[0] > 0:
            await send_message_with_retry(
                message.bot,
                message.chat.id,
                "Такой товар уже существует!",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Назад", callback_data="back_to_admin")]
                ])
            )
            await state.clear()
            return
        await db.execute(
            """
            INSERT INTO products (name, desc, price, category_id, subcategory_id, delivery_file, media)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data["name"],
                data.get("desc"),
                data["price"],
                data["category_id"],
                data.get("subcategory_id"),
                delivery_file,
                data.get("media")
            )
        )
        await db.commit()
    
    logging.info(f"Product added: {data['name']} by user {message.from_user.id}")
    await send_message_with_retry(
        message.bot,
        message.chat.id,
        f"Товар *{data['name']}* добавлен!",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Назад", callback_data="back_to_admin")]
        ]),
        parse_mode="Markdown"
    )
    await state.clear()

@router.callback_query(F.data == "add_product_name")
async def back_to_product_name(callback: CallbackQuery, state: FSMContext):
    await edit_message_with_retry(
        callback.message,
        "Введите название товара:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Назад", callback_data="back_to_admin")]
        ])
    )
    await state.set_state(AdminStates.ADD_PRODUCT_NAME)

@router.callback_query(F.data == "add_product_desc")
async def back_to_product_desc(callback: CallbackQuery, state: FSMContext):
    await edit_message_with_retry(
        callback.message,
        "Введите описание товара (или /skip, чтобы пропустить):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Назад", callback_data="add_product")]
        ])
    )
    await state.set_state(AdminStates.ADD_PRODUCT_DESC)

@router.callback_query(F.data == "add_product_price")
async def back_to_product_price(callback: CallbackQuery, state: FSMContext):
    await edit_message_with_retry(
        callback.message,
        "Введите цену товара в $ (0 для бесплатных):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Назад", callback_data="add_product_desc")]
        ])
    )
    await state.set_state(AdminStates.ADD_PRODUCT_PRICE)

@router.callback_query(F.data == "add_product_category")
async def back_to_product_category(callback: CallbackQuery, state: FSMContext):
    categories = await get_categories()
    kb_buttons = [[InlineKeyboardButton(text=cat[1], callback_data=f"cat_{cat[0]}")] for cat in categories]
    kb_buttons.append([InlineKeyboardButton(text="Назад", callback_data="add_product_price")])
    kb = InlineKeyboardMarkup(inline_keyboard=kb_buttons)
    await edit_message_with_retry(callback.message, "Выберите категорию товара:", reply_markup=kb)
    await state.set_state(AdminStates.ADD_PRODUCT_CATEGORY)

@router.callback_query(F.data == "add_product_subcategory")
async def back_to_product_subcategory(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    subcategories = await get_categories(data["category_id"])
    kb_buttons = [[InlineKeyboardButton(text="Без подкатегории", callback_data="no_subcategory")]]
    kb_buttons.extend([[InlineKeyboardButton(text=subcat[1], callback_data=f"subcat_{subcat[0]}")] for subcat in subcategories])
    kb_buttons.append([InlineKeyboardButton(text="Назад", callback_data="add_product_category")])
    kb = InlineKeyboardMarkup(inline_keyboard=kb_buttons)
    await edit_message_with_retry(callback.message, "Выберите подкатегорию (или 'Без подкатегории'):", reply_markup=kb)
    await state.set_state(AdminStates.ADD_PRODUCT_SUBCATEGORY)

@router.callback_query(F.data == "add_product_media")
async def back_to_product_media(callback: CallbackQuery, state: FSMContext):
    await edit_message_with_retry(
        callback.message,
        "Отправьте фото или гиф для карточки товара (или /skip, чтобы пропустить):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Назад", callback_data="add_product_subcategory")]
        ])
    )
    await state.set_state(AdminStates.ADD_PRODUCT_MEDIA)

@router.callback_query(F.data == "list_products", AdminStates.MAIN)
async def list_products(callback: CallbackQuery, state: FSMContext):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT p.id, p.name, p.price, c.name, s.name
            FROM products p
            JOIN categories c ON p.category_id = c.id
            LEFT JOIN categories s ON p.subcategory_id = s.id
        """)
        products = await cursor.fetchall()
    
    if not products:
        await edit_message_with_retry(
            callback.message,
            "Товаров нет.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Назад", callback_data="back_to_admin")]
            ])
        )
        return
    
    text = "Список товаров:\n\n"
    for product in products:
        product_id, name, price, category, subcategory = product
        text += f"ID: {product_id} | {name} | {price}$ | {category}"
        if subcategory:
            text += f" / {subcategory}"
        text += "\n"
    
    await edit_message_with_retry(
        callback.message,
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Назад", callback_data="back_to_admin")]
        ])
    )

@router.callback_query(F.data == "delete_product", AdminStates.MAIN)
async def delete_product_start(callback: CallbackQuery, state: FSMContext):
    await edit_message_with_retry(
        callback.message,
        "Введите ID товара для удаления:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Назад", callback_data="back_to_admin")]
        ])
    )
    await state.set_state(AdminStates.DELETE_PRODUCT)

@router.message(AdminStates.DELETE_PRODUCT)
async def delete_product(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await send_message_with_retry(
            message.bot,
            message.chat.id,
            "Доступ запрещён.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Назад", callback_data="back_to_main")]
            ])
        )
        await state.clear()
        return
    
    try:
        product_id = int(message.text)
        async with aiosqlite.connect(DB_PATH) as db:
            # Проверяем, есть ли товар
            cursor = await db.execute("SELECT name FROM products WHERE id = ?", (product_id,))
            product = await cursor.fetchone()
            if not product:
                await send_message_with_retry(
                    message.bot,
                    message.chat.id,
                    f"Товар с ID {product_id} не найден!",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="Назад", callback_data="back_to_admin")]
                    ])
                )
                await state.clear()
                return
            
            # Удаляем из корзины
            await db.execute("DELETE FROM cart WHERE product_id = ?", (product_id,))
            # Удаляем из заказов
            await db.execute("DELETE FROM orders WHERE product_id = ?", (product_id,))
            # Удаляем из invoices
            await db.execute("DELETE FROM invoices WHERE product_id = ?", (product_id,))
            # Удаляем сам товар
            await db.execute("DELETE FROM products WHERE id = ?", (product_id,))
            await db.commit()
        
        await send_message_with_retry(
            message.bot,
            message.chat.id,
            f"Товар '{product[0]}' (ID: {product_id}) удалён!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Назад", callback_data="back_to_admin")]
            ])
        )
    except ValueError:
        await send_message_with_retry(
            message.bot,
            message.chat.id,
            "ID должен быть числом. Попробуй снова:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Назад", callback_data="back_to_admin")]
            ])
        )
    await state.clear()

@router.callback_query(F.data == "edit_product", AdminStates.MAIN)
async def edit_product_start(callback: CallbackQuery, state: FSMContext):
    await edit_message_with_retry(
        callback.message,
        "Введите ID товара для редактирования:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Назад", callback_data="back_to_admin")]
        ])
    )
    await state.set_state(AdminStates.EDIT_PRODUCT)

@router.message(AdminStates.EDIT_PRODUCT)
async def edit_product(message: Message, state: FSMContext):
    try:
        product_id = int(message.text)
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM products WHERE id = ?", (product_id,))
            if (await cursor.fetchone())[0] == 0:
                await send_message_with_retry(
                    message.bot,
                    message.chat.id,
                    "Товар не найден!",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="Назад", callback_data="back_to_admin")]
                    ])
                )
                await state.clear()
                return
        await state.update_data(product_id=product_id)
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Название", callback_data="edit_name")],
            [InlineKeyboardButton(text="Описание", callback_data="edit_desc")],
            [InlineKeyboardButton(text="Цена", callback_data="edit_price")],
            [InlineKeyboardButton(text="Категория", callback_data="edit_category")],
            [InlineKeyboardButton(text="Подкатегория", callback_data="edit_subcategory")],
            [InlineKeyboardButton(text="Файл/текст доставки", callback_data="edit_delivery_file")],
            [InlineKeyboardButton(text="Фото/гиф карточки", callback_data="edit_media")],
            [InlineKeyboardButton(text="Назад", callback_data="back_to_admin")]
        ])
        await send_message_with_retry(
            message.bot,
            message.chat.id,
            "Что изменить?",
            reply_markup=kb
        )
        await state.set_state(AdminStates.EDIT_PRODUCT_FIELD)
    except ValueError:
        await send_message_with_retry(
            message.bot,
            message.chat.id,
            "ID должен быть числом. Попробуй снова:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Назад", callback_data="back_to_admin")]
            ])
        )

@router.callback_query(F.data.startswith("edit_"), AdminStates.EDIT_PRODUCT_FIELD)
async def edit_product_field(callback: CallbackQuery, state: FSMContext):
    field = callback.data.split("_")[1]
    await state.update_data(field=field)
    fields = {
        "name": "Введите новое название:",
        "desc": "Введите новое описание (или /skip, чтобы удалить):",
        "price": "Введите новую цену в $:",
        "category": "Выберите новую категорию:",
        "subcategory": "Выберите новую подкатегорию (или 'Без подкатегории'):",
        "delivery_file": "Отправьте новый текст, фото, гиф или файл для доставки (или /skip, чтобы удалить):",
        "media": "Отправьте новое фото или гиф для карточки (или /skip, чтобы удалить):"
    }
    if field in ["category", "subcategory"]:
        categories = await get_categories() if field == "category" else await get_categories((await state.get_data())["category_id"])
        if not categories and field == "category":
            await edit_message_with_retry(
                callback.message,
                "Нет категорий. Создайте категорию в 'Управление категориями'.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Назад", callback_data="back_to_admin")]
                ])
            )
            await state.clear()
            return
        kb_buttons = [[InlineKeyboardButton(text=cat[1], callback_data=f"new_{field}_{cat[0]}")] for cat in categories]
        if field == "subcategory":
            kb_buttons.append([InlineKeyboardButton(text="Без подкатегории", callback_data="new_subcategory_none")])
        kb_buttons.append([InlineKeyboardButton(text="Назад", callback_data="edit_product")])
        kb = InlineKeyboardMarkup(inline_keyboard=kb_buttons)
        await edit_message_with_retry(callback.message, fields[field], reply_markup=kb)
    else:
        await edit_message_with_retry(
            callback.message,
            fields[field],
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Назад", callback_data="edit_product")]
            ])
        )
    await state.set_state(AdminStates.EDIT_PRODUCT_FIELD)

@router.message(AdminStates.EDIT_PRODUCT_FIELD)
async def update_product_field(message: Message, state: FSMContext):
    data = await state.get_data()
    product_id = data["product_id"]
    field = data["field"]
    async with aiosqlite.connect(DB_PATH) as db:
        if field == "price":
            try:
                value = float(message.text)
                if value < 0:
                    await send_message_with_retry(
                        message.bot,
                        message.chat.id,
                        "Цена должна быть числом >= 0. Попробуй снова:",
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="Назад", callback_data="edit_product")]
                        ])
                    )
                    return
            except ValueError:
                await send_message_with_retry(
                    message.bot,
                    message.chat.id,
                    "Цена должна быть числом >= 0. Попробуй снова:",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="Назад", callback_data="edit_product")]
                    ])
                )
                return
        elif field == "delivery_file" and message.text != "/skip":
            if message.text:
                value = message.text
            elif message.photo:
                value = message.photo[-1].file_id
            elif message.animation:
                value = message.animation.file_id
            elif message.document:
                value = message.document.file_id
            else:
                await send_message_with_retry(
                    message.bot,
                    message.chat.id,
                    "Отправьте текст, фото, гиф или файл (или /skip):",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="Назад", callback_data="edit_product")]
                    ])
                )
                return
        elif field == "media" and message.text != "/skip":
            if message.photo:
                value = message.photo[-1].file_id
            elif message.animation:
                value = message.animation.file_id
            else:
                await send_message_with_retry(
                    message.bot,
                    message.chat.id,
                    "Отправьте фото или гиф (или /skip):",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="Назад", callback_data="edit_product")]
                    ])
                )
                return
        else:
            value = message.text if message.text != "/skip" else None
        
        await db.execute(f"UPDATE products SET {field} = ? WHERE id = ?", (value, product_id))
        await db.commit()
    
    await send_message_with_retry(
        message.bot,
        message.chat.id,
        "Товар обновлён!",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Назад", callback_data="back_to_admin")]
        ])
    )
    await state.clear()

@router.callback_query(F.data.startswith("new_category_"), AdminStates.EDIT_PRODUCT_FIELD)
async def update_product_category(callback: CallbackQuery, state: FSMContext):
    category_id = int(callback.data.split("_")[2])
    product_id = (await state.get_data())["product_id"]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE products SET category_id = ?, subcategory_id = NULL WHERE id = ?", (category_id, product_id))
        await db.commit()
    await edit_message_with_retry(
        callback.message,
        "Категория обновлена!",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Назад", callback_data="back_to_admin")]
        ])
    )
    await state.clear()

@router.callback_query(F.data.startswith("new_subcategory_"), AdminStates.EDIT_PRODUCT_FIELD)
async def update_product_subcategory(callback: CallbackQuery, state: FSMContext):
    subcategory_id = None if callback.data == "new_subcategory_none" else int(callback.data.split("_")[2])
    product_id = (await state.get_data())["product_id"]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE products SET subcategory_id = ? WHERE id = ?", (subcategory_id, product_id))
        await db.commit()
    await edit_message_with_retry(
        callback.message,
        "Подкатегория обновлена!",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Назад", callback_data="back_to_admin")]
        ])
    )
    await state.clear()

@router.callback_query(F.data == "add_promocode", AdminStates.MAIN)
async def add_promocode_start(callback: CallbackQuery, state: FSMContext):
    await edit_message_with_retry(
        callback.message,
        "Введите код промокода:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Назад", callback_data="back_to_admin")]
        ])
    )
    await state.set_state(AdminStates.ADD_PROMOCODE_CODE)

@router.message(AdminStates.ADD_PROMOCODE_CODE)
async def add_promocode_code(message: Message, state: FSMContext):
    await state.update_data(code=message.text)
    await send_message_with_retry(
        message.bot,
        message.chat.id,
        "Введите процент скидки (0-100):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Назад", callback_data="add_promocode")]
        ])
    )
    await state.set_state(AdminStates.ADD_PROMOCODE_DISCOUNT)

@router.message(AdminStates.ADD_PROMOCODE_DISCOUNT)
async def add_promocode_discount(message: Message, state: FSMContext):
    try:
        discount = int(message.text)
        if not 0 <= discount <= 100:
            raise ValueError
        await state.update_data(discount=discount)
        await send_message_with_retry(
            message.bot,
            message.chat.id,
            "Введите максимальное количество использований (или /skip для бесконечности):",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Назад", callback_data="add_promocode_code")]
            ])
        )
        await state.set_state(AdminStates.ADD_PROMOCODE_MAX_USES)
    except ValueError:
        await send_message_with_retry(
            message.bot,
            message.chat.id,
            "Скидка должна быть числом от 0 до 100. Попробуй снова:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Назад", callback_data="add_promocode")]
            ])
        )

@router.message(AdminStates.ADD_PROMOCODE_MAX_USES)
async def add_promocode_max_uses(message: Message, state: FSMContext):
    data = await state.get_data()
    max_uses = None
    if message.text != "/skip":
        try:
            max_uses = int(message.text)
            if max_uses <= 0:
                raise ValueError
        except ValueError:
            await send_message_with_retry(
                message.bot,
                message.chat.id,
                "Количество использований должно быть числом > 0 или /skip. Попробуй снова:",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Назад", callback_data="add_promocode_discount")]
                ])
            )
            return
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute(
                "INSERT INTO promocodes (code, discount_percent, max_uses) VALUES (?, ?, ?)",
                (data["code"], data["discount"], max_uses)
            )
            await db.commit()
            await send_message_with_retry(
                message.bot,
                message.chat.id,
                "Промокод добавлен!",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Назад", callback_data="back_to_admin")]
                ])
            )
        except aiosqlite.IntegrityError:
            await send_message_with_retry(
                message.bot,
                message.chat.id,
                "Промокод с таким кодом уже существует!",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Назад", callback_data="back_to_admin")]
                ])
            )
    await state.clear()

@router.callback_query(F.data == "discounts", AdminStates.MAIN)
async def discounts(callback: CallbackQuery, state: FSMContext):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT code, discount_percent, max_uses, uses_count FROM promocodes")
        promocodes = await cursor.fetchall()
    
    text = "*Промокоды*\n\n"
    if not promocodes:
        text += "Промокодов нет.\n"
    for promo in promocodes:
        code, discount, max_uses, uses_count = promo
        code_esc = code.replace('.', '\\.')
        discount_esc = str(discount).replace('.', '\\.')
        uses_count_esc = str(uses_count).replace('.', '\\.')
        max_uses_esc = str(max_uses).replace('.', '\\.') if max_uses else '∞'
        text += f"Код: {code_esc} | Скидка: {discount_esc}% | Использовано: {uses_count_esc}/{max_uses_esc}\n"
    
    await edit_message_with_retry(
        callback.message,
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Назад", callback_data="back_to_admin")]
        ]),
        parse_mode="MarkdownV2"
    )

@router.callback_query(F.data == "stats", AdminStates.MAIN)
async def stats(callback: CallbackQuery, state: FSMContext):
    async with aiosqlite.connect(DB_PATH) as db:
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
        
        cursor = await db.execute("SELECT code, discount_percent, max_uses, uses_count FROM promocodes")
        promocodes = await cursor.fetchall()
    
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
    
    await edit_message_with_retry(
        callback.message,
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Назад", callback_data="back_to_admin")]
        ]),
        parse_mode="MarkdownV2"
    )

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
    await edit_message_with_retry(callback.message, "Админ-панель:", reply_markup=kb)
    await state.set_state(AdminStates.MAIN)