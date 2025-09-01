from aiogram import Bot, F, Router, types, Dispatcher
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from db import DB_PATH, get_user, add_user, get_purchases_count, get_cart_items, remove_from_cart
from config import ADMIN_ID, CHANNEL_ID, CHAT_ID, CHANNEL_INVITE, CHAT_INVITE
from payments import send_payment_request, check_invoice
import aiosqlite
import logging


router = Router()

# Состояния для FSM
class UserStates(StatesGroup):
    MAIN_MENU = State()

class CartStates(StatesGroup):
    VIEW = State()
    SELECT_ITEM = State()

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


class CatalogStates(StatesGroup):
    CATEGORY = State()
    SUBCATEGORY = State()
    PRODUCT = State()

class TopUpStates(StatesGroup):
    ENTER_AMOUNT = State()

def get_main_menu(is_admin: bool = False) -> ReplyKeyboardMarkup:
    """Главное меню"""
    kb = [
        [KeyboardButton(text="Товары"), KeyboardButton(text="Профиль")],
        [KeyboardButton(text="Корзина"), KeyboardButton(text="Инструкция")]
    ]
    if is_admin:
        kb.append([KeyboardButton(text="Админ-панель")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_subscription_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для проверки подписки"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Подписаться на канал", url=CHANNEL_INVITE)],
        [InlineKeyboardButton(text="Подписаться на чат", url=CHAT_INVITE)],
        [InlineKeyboardButton(text="Проверить подписку", callback_data="check_subscription")],
        [InlineKeyboardButton(text="Назад", callback_data="back_to_start")]
    ])

async def check_subscription(bot: Bot, user_id: int) -> bool:
    """Проверка подписки на канал и чат"""
    try:
        channel_member = await bot.get_chat_member(CHANNEL_ID, user_id)
        chat_member = await bot.get_chat_member(CHAT_ID, user_id)
        return channel_member.status != "left" and chat_member.status != "left"
    except Exception as e:
        logging.error(f"Error checking subscription: {e}")
        return False

@router.callback_query(F.data == "check_subscription")
async def check_subscription_callback(callback: CallbackQuery, bot: Bot, state: FSMContext):
    user_id = callback.from_user.id
    if await check_subscription(bot, user_id):
        is_admin = user_id == ADMIN_ID
        await callback.message.edit_text(
            "Спасибо за подписку! Выбери действие:",
            reply_markup=get_main_menu(is_admin)
        )
        await state.set_state(UserStates.MAIN_MENU)
        await callback.answer()
    else:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Подписаться на канал", url=CHANNEL_INVITE)],
            [InlineKeyboardButton(text="Подписаться на чат", url=CHAT_INVITE)],
            [InlineKeyboardButton(text="Проверить подписку", callback_data="check_subscription")],
            [InlineKeyboardButton(text="Назад", callback_data="back_to_start")]
        ])
        await callback.answer(
            "Ты ещё не подписан на канал или чат! Подпишись и попробуй снова.",
            show_alert=True
        )
        await callback.message.edit_text(
            "Ты ещё не подписан на канал или чат! Подпишись и попробуй снова:",
            reply_markup=kb
        )

@router.callback_query(F.data == "back_to_start")
async def back_to_start(callback: CallbackQuery, bot: Bot, state: FSMContext):
    is_admin = callback.from_user.id == ADMIN_ID
    await callback.message.delete()
    await callback.message.answer(
        "Добро пожаловать в мощный шоп от DROPZONE! 🚀",
        reply_markup=get_main_menu(is_admin)
    )
    await state.set_state(UserStates.MAIN_MENU)
    await callback.answer()

@router.message(Command("start"))
async def start_command(message: Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id
    if not await check_subscription(bot, user_id):
        await message.answer(
            "Для использования бота подпишись на наш канал и чат!",
            reply_markup=get_subscription_keyboard()
        )
        return
    
    ref_id = None
    if len(message.text.split()) > 1 and message.text.split()[1].startswith("ref_"):
        ref_id = int(message.text.split()[1].replace("ref_", ""))
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT OR IGNORE INTO referrals (user_id, ref_user_id) VALUES (?, ?)",
                (user_id, ref_id)
            )
            await db.commit()
    
    if not await get_user(user_id):
        await add_user(user_id, ref_id)
    
    is_admin = user_id == ADMIN_ID
    await message.answer(
        "Добро пожаловать в мощный шоп от DROPZONE! 🚀",
        reply_markup=get_main_menu(is_admin)
    )
    await state.set_state(UserStates.MAIN_MENU)

@router.message(Command("catalog"))
@router.message(F.text == "Товары")
async def products_command(message: Message, bot: Bot, state: FSMContext):
    if not await check_subscription(bot, message.from_user.id):
        await message.answer(
            "Подпишись на канал и чат!",
            reply_markup=get_subscription_keyboard()
        )
        return
    
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT DISTINCT category FROM products")
        categories = [row[0] for row in await cursor.fetchall()]
    
    if not categories:
        is_admin = message.from_user.id == ADMIN_ID
        await message.answer("Каталог пуст.", reply_markup=get_main_menu(is_admin))
        return
    
    kb_buttons = [[InlineKeyboardButton(text=cat, callback_data=f"category_{cat}")] for cat in categories]
    kb_buttons.append([InlineKeyboardButton(text="Назад", callback_data="back_to_main")])
    kb = InlineKeyboardMarkup(inline_keyboard=kb_buttons)
    await message.answer("Каталог:", reply_markup=kb)
    await state.set_state(CatalogStates.CATEGORY)

async def show_categories(message: Message, bot: Bot, state: FSMContext):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT DISTINCT category FROM products")
        categories = [row[0] for row in await cursor.fetchall()]
    
    if not categories:
        is_admin = message.from_user.id == ADMIN_ID
        await message.answer("Каталог пуст.", reply_markup=get_main_menu(is_admin))
        return
    
    kb_buttons = [[InlineKeyboardButton(text=cat, callback_data=f"category_{cat}")] for cat in categories]
    kb_buttons.append([InlineKeyboardButton(text="Назад", callback_data="back_to_main")])
    kb = InlineKeyboardMarkup(inline_keyboard=kb_buttons)
    await message.answer("Каталог:", reply_markup=kb)
    await state.set_state(CatalogStates.CATEGORY)

@router.callback_query(F.data.startswith("category_"))
async def show_subcategories(callback: CallbackQuery, bot: Bot, state: FSMContext):
    category = callback.data.split("_")[1]
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT DISTINCT subcategory FROM products WHERE category = ?", (category,))
        subcategories = [row[0] for row in await cursor.fetchall() if row[0]]
    
    if not subcategories:
        await show_products(callback, bot, state, category)
        return
    
    kb_buttons = [[InlineKeyboardButton(text=subcat, callback_data=f"subcategory_{category}_{subcat}")] for subcat in subcategories]
    kb_buttons.append([InlineKeyboardButton(text="Назад", callback_data="back_to_catalog")])
    kb = InlineKeyboardMarkup(inline_keyboard=kb_buttons)
    await callback.message.edit_text(f"Подкатегории в {category}:", reply_markup=kb)
    await state.set_state(CatalogStates.SUBCATEGORY)

async def show_products(callback: CallbackQuery, bot: Bot, state: FSMContext, category: str, subcategory: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        if subcategory:
            cursor = await db.execute("SELECT id, name, price FROM products WHERE category = ? AND subcategory = ?", (category, subcategory,))
        else:
            cursor = await db.execute("SELECT id, name, price FROM products WHERE category = ?", (category,))
        products = await cursor.fetchall()
    
    user = await get_user(callback.from_user.id)
    discount = user['discount'] if user else 0
    
    text = f"Продукты в категории {category}{f' ({subcategory})' if subcategory else ''}:\n\n"
    kb_buttons = []
    for product in products:
        product_id, name, price = product
        final_price = price * (1 - discount / 100)
        kb_buttons.append([InlineKeyboardButton(text=f"{name} {final_price}$", callback_data=f"product_{product_id}")])
    
    kb_buttons.append([InlineKeyboardButton(text="Назад", callback_data=f"back_to_subcategory_{category}_{subcategory}" if subcategory else "back_to_catalog")])
    kb = InlineKeyboardMarkup(inline_keyboard=kb_buttons)
    await callback.message.edit_text(text, reply_markup=kb)
    await state.set_state(CatalogStates.PRODUCT)

@router.callback_query(F.data.startswith("product_"))
async def show_product_card(callback: CallbackQuery, bot: Bot, state: FSMContext):
    product_id = int(callback.data.split("_")[1])
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT name, desc, price, category, subcategory FROM products WHERE id = ?", (product_id,))
        product = await cursor.fetchone()
    
    if product:
        name, desc, price, category, subcategory = product
        user = await get_user(callback.from_user.id)
        discount = user['discount'] if user else 0
        final_price = price * (1 - discount / 100)
        text = f"*{name}*\n\n{desc}\n\nКатегория: {category}\n" + \
               (f"Подкатегория: {subcategory}\n" if subcategory else "") + \
               f"Цена: {final_price}$"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Купить", callback_data=f"buy_product_{product_id}")],
            [InlineKeyboardButton(text="В корзину", callback_data=f"add_to_cart_{product_id}")],
            [InlineKeyboardButton(text="Назад", callback_data=f"back_to_subcategory_{category}_{subcategory}" if subcategory else f"back_to_category_{category}")]
        ])
        await callback.message.edit_text(text, reply_markup=kb)
        await state.update_data(category=category, subcategory=subcategory)
        await state.set_state(CatalogStates.PRODUCT)
    else:
        await callback.answer("Товар не найден.", show_alert=True)

@router.callback_query(F.data.startswith("back_to_subcategory_"))
async def back_to_subcategory(callback: CallbackQuery, bot: Bot, state: FSMContext):
    data = callback.data.split("_")[3:]
    category, subcategory = data[0], data[1]
    await callback.message.delete()
    await show_products(callback, bot, state, category, subcategory)

@router.callback_query(F.data.startswith("back_to_category_"))
async def back_to_category(callback: CallbackQuery, bot: Bot, state: FSMContext):
    category = callback.data.split("_")[-1]
    await callback.message.delete()
    await show_subcategories(callback, bot, state)

@router.callback_query(F.data == "back_to_catalog")
async def back_to_catalog(callback: CallbackQuery, bot: Bot, state: FSMContext):
    await callback.message.delete()
    await show_categories(callback.message, bot, state)

@router.message(Command("profile"))
@router.message(F.text == "Профиль")
async def profile_command(message: Message, bot: Bot):
    if not await check_subscription(bot, message.from_user.id):
        await message.answer(
            "Подпишись на канал и чат!",
            reply_markup=get_subscription_keyboard()
        )
        return
    
    user = await get_user(message.from_user.id)
    if not user:
        is_admin = message.from_user.id == ADMIN_ID
        await message.answer("Ошибка: пользователь не найден.", reply_markup=get_main_menu(is_admin))
        return
    
    username = message.from_user.username or "Не указан"
    ref_link = f"t.me/{(await bot.get_me()).username}?start=ref_{message.from_user.id}"
    purchases_count = await get_purchases_count(message.from_user.id)
    is_admin = message.from_user.id == ADMIN_ID
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пополнить", callback_data="top_up")],
        [InlineKeyboardButton(text="Корзина", callback_data="cart")],
        [InlineKeyboardButton(text="Ввести промокод", callback_data="enter_promocode")],
        [InlineKeyboardButton(text="История покупок", callback_data="history")],
        [InlineKeyboardButton(text="Мои рефералы", callback_data="referrals_list")],
        [InlineKeyboardButton(text="Назад", callback_data="back_to_main")]
    ])
    await message.answer(
        f"*Профиль*\n\n"
        f"Имя: @{username}\n"
        f"Баланс: {user['balance']}$\n"
        f"Ваша скидка: {user['discount']}% (активируйте промокод для скидки)\n"
        f"Покупок: {purchases_count}\n\n"
        f"Реферальная ссылка: {ref_link}\n"
        f"Рефералов приглашено: {user['referrals_count']}\n"
        f"Заработано на рефералах: {user['earnings']}$",
        reply_markup=kb
    )

@router.message(Command("cart"))
@router.message(F.text == "Корзина")
async def cart_command(message: Message, bot: Bot, state: FSMContext):
    if not await check_subscription(bot, message.from_user.id):
        await message.answer(
            "Подпишись на канал и чат!",
            reply_markup=get_subscription_keyboard()
        )
        return
    
    cart_items = await get_cart_items(message.from_user.id)
    if not cart_items:
        is_admin = message.from_user.id == ADMIN_ID
        await message.answer("Ваша корзина пуста.", reply_markup=get_main_menu(is_admin))
        return
    
    text = "Ваша корзина:\n\n"
    total = 0
    kb_buttons = []
    user = await get_user(message.from_user.id)
    discount = user['discount'] if user else 0
    for item in cart_items:
        product_id, name, price = item
        final_price = price * (1 - discount / 100)
        text += f"{name} = {final_price}$\n"
        total += final_price
        kb_buttons.append([
            InlineKeyboardButton(text="Оплатить", callback_data=f"pay_item_{product_id}"),
            InlineKeyboardButton(text="Удалить", callback_data=f"delete_item_{product_id}")
        ])
    
    text += f"\nИтого: {total}$"
    kb_buttons.extend([
        [InlineKeyboardButton(text="Оплатить всю", callback_data="pay_all")],
        [InlineKeyboardButton(text="Очистить всю", callback_data="clear_cart")],
        [InlineKeyboardButton(text="Назад", callback_data="back_to_main")]
    ])
    kb = InlineKeyboardMarkup(inline_keyboard=kb_buttons)
    await message.answer(text, reply_markup=kb)
    await state.set_state(CartStates.VIEW)

@router.callback_query(F.data == "top_up")
async def top_up(callback: CallbackQuery, bot: Bot, state: FSMContext):
    if not await check_subscription(bot, callback.from_user.id):
        await callback.message.edit_text(
            "Подпишись на канал и чат!",
            reply_markup=get_subscription_keyboard()
        )
        await callback.answer()
        return
    
    await callback.message.delete()
    await callback.message.answer("Введите сумму пополнения в $:")
    await state.set_state(TopUpStates.ENTER_AMOUNT)

@router.message(TopUpStates.ENTER_AMOUNT)
async def process_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text)
        if amount <= 0:
            raise ValueError
        user_id = message.from_user.id
        invoice_id = await send_payment_request(message.bot, user_id, 0, amount)
        if invoice_id:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Оплатить", url=f"https://t.me/CryptoBot?start=inv_{invoice_id}")]
            ])
            is_admin = user_id == ADMIN_ID
            await message.answer("Нажмите, чтобы оплатить:", reply_markup=kb)
            await message.answer("После оплаты вернитесь и проверьте баланс.", reply_markup=get_main_menu(is_admin))
        else:
            is_admin = user_id == ADMIN_ID
            await message.answer("Ошибка при создании платежа.", reply_markup=get_main_menu(is_admin))
        await state.clear()
    except ValueError:
        await message.answer("Сумма должна быть числом больше 0. Попробуй снова:")

@router.callback_query(F.data.startswith("buy_product_"))
async def buy_product(callback: CallbackQuery, bot: Bot, state: FSMContext):
    user_id = callback.from_user.id
    if not await check_subscription(bot, user_id):
        await callback.message.edit_text(
            "Подпишись на канал и чат!",
            reply_markup=get_subscription_keyboard()
        )
        await callback.answer()
        return
    
    product_id = int(callback.data.split("_")[2])
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT id, price, name FROM products WHERE id = ?", (product_id,))
        product = await cursor.fetchone()
        if product:
            product_id, amount_usd, name = product
            user = await get_user(user_id)
            discount = user['discount'] if user else 0
            amount_usd = amount_usd * (1 - discount / 100)
            invoice_id = await send_payment_request(bot, user_id, product_id, amount_usd)
            if invoice_id:
                kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Оплатить", url=f"https://t.me/CryptoBot?start=inv_{invoice_id}")]
                ])
                await callback.message.edit_text(
                    f"Оплатите товар *{name}* за {amount_usd}$:",
                    reply_markup=kb
                )
                await callback.answer("Платёж создан! Проверьте ссылку выше.")
            else:
                await callback.answer("Ошибка при создании платежа.", show_alert=True)
        else:
            await callback.answer("Товар не найден.", show_alert=True)

@router.callback_query(F.data.startswith("pay_item_"))
async def pay_item(callback: CallbackQuery, bot: Bot, state: FSMContext):
    user_id = callback.from_user.id
    if not await check_subscription(bot, user_id):
        await callback.message.edit_text(
            "Подпишись на канал и чат!",
            reply_markup=get_subscription_keyboard()
        )
        await callback.answer()
        return
    
    product_id = int(callback.data.split("_")[2])
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT id, price, name FROM products WHERE id = ?", (product_id,))
        product = await cursor.fetchone()
        if product:
            product_id, amount_usd, name = product
            user = await get_user(user_id)
            discount = user['discount'] if user else 0
            amount_usd = amount_usd * (1 - discount / 100)
            invoice_id = await send_payment_request(bot, user_id, product_id, amount_usd)
            if invoice_id:
                kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Оплатить", url=f"https://t.me/CryptoBot?start=inv_{invoice_id}")]
                ])
                await callback.message.edit_text(
                    f"Оплатите товар *{name}* за {amount_usd}$:",
                    reply_markup=kb
                )
                await callback.answer("Платёж создан! Проверьте ссылку выше.")
                await remove_from_cart(user_id, product_id)
            else:
                await callback.answer("Ошибка при создании платежа.", show_alert=True)
        else:
            await callback.answer("Товар не найден.", show_alert=True)

@router.callback_query(F.data.startswith("add_to_cart_"))
async def add_to_cart(callback: CallbackQuery, bot: Bot, state: FSMContext):
    user_id = callback.from_user.id
    if not await check_subscription(bot, user_id):
        await callback.message.edit_text(
            "Подпишись на канал и чат!",
            reply_markup=get_subscription_keyboard()
        )
        await callback.answer()
        return
    
    product_id = int(callback.data.split("_")[2])
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO cart (user_id, product_id, quantity) VALUES (?, ?, ?)",
            (user_id, product_id, 1)
        )
        await db.commit()
    await callback.answer("Товар добавлен в корзину!", show_alert=True)

@router.callback_query(F.data.startswith("delete_item_"))
async def delete_item(callback: CallbackQuery, bot: Bot, state: FSMContext):
    user_id = callback.from_user.id
    if not await check_subscription(bot, user_id):
        await callback.message.edit_text(
            "Подпишись на канал и чат!",
            reply_markup=get_subscription_keyboard()
        )
        await callback.answer()
        return
    
    product_id = int(callback.data.split("_")[2])
    await remove_from_cart(user_id, product_id)
    await callback.answer("Товар удалён из корзины!", show_alert=True)
    await cart_command(callback.message, bot, state)

@router.callback_query(F.data == "clear_cart")
async def clear_cart(callback: CallbackQuery, bot: Bot, state: FSMContext):
    user_id = callback.from_user.id
    if not await check_subscription(bot, user_id):
        await callback.message.edit_text(
            "Подпишись на канал и чат!",
            reply_markup=get_subscription_keyboard()
        )
        await callback.answer()
        return
    
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM cart WHERE user_id = ?", (user_id,))
        await db.commit()
    is_admin = user_id == ADMIN_ID
    await callback.message.delete()
    await callback.message.answer("Корзина очищена!", reply_markup=get_main_menu(is_admin))
    await state.set_state(UserStates.MAIN_MENU)

@router.message(Command("help"))
@router.message(F.text == "Инструкция")
async def support_command(message: Message, bot: Bot):
    if not await check_subscription(bot, message.from_user.id):
        await message.answer(
            "Подпишись на канал и чат!",
            reply_markup=get_subscription_keyboard()
        )
        return
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Чат с админом", url="t.me/+your_admin_chat")],
        [InlineKeyboardButton(text="FAQ", callback_data="faq")]
    ])
    await message.answer("Как можем помочь?", reply_markup=kb)

@router.message(F.text == "Рефералы")
async def referrals_command(message: Message, bot: Bot):
    if not await check_subscription(bot, message.from_user.id):
        await message.answer(
            "Подпишись на канал и чат!",
            reply_markup=get_subscription_keyboard()
        )
        return
    
    user = await get_user(message.from_user.id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Список рефералов", callback_data="referrals_list")]
    ])
    await message.answer(
        f"Рефералы:\nВсего: {user['referrals_count']}\nЗаработок: {user['earnings']}$",
        reply_markup=kb
    )

@router.callback_query(F.data == "referrals_list")
async def referrals_list_command(callback: CallbackQuery, bot: Bot, state: FSMContext):
    user_id = callback.from_user.id
    if not await check_subscription(bot, user_id):
        await callback.message.edit_text(
            "Подпишись на канал и чат!",
            reply_markup=get_subscription_keyboard()
        )
        await callback.answer()
        return
    
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT u.id, u.created_at
            FROM referrals r JOIN users u ON r.user_id = u.id
            WHERE r.ref_user_id = ?
        """, (user_id,))
        referrals = await cursor.fetchall()
    
    is_admin = user_id == ADMIN_ID
    if not referrals:
        await callback.message.delete()
        await callback.message.answer(
            "У вас нет рефералов.",
            reply_markup=get_main_menu(is_admin)
        )
        return
    
    text = "Ваши рефералы:\n\n"
    for ref in referrals:
        ref_id, created_at = ref
        text += f"Юзер {ref_id}, зарегистрирован: {created_at}\n"
    
    await callback.message.delete()
    await callback.message.answer(text, reply_markup=get_main_menu(is_admin))
    await callback.answer()

@router.message(Command("admin"))
@router.message(F.text == "Админ-панель")
async def admin_command(message: Message, bot: Bot, state: FSMContext):
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

@router.callback_query(F.data == "back_to_main")
async def back_to_main(callback: CallbackQuery, bot: Bot, state: FSMContext):
    user_id = callback.from_user.id
    is_admin = user_id == ADMIN_ID
    await callback.message.delete()
    await callback.message.answer(
        "Добро пожаловать в мощный шоп от DROPZONE! 🚀",
        reply_markup=get_main_menu(is_admin)
    )
    await state.set_state(UserStates.MAIN_MENU)
    await callback.answer()

def register_handlers(dp: Dispatcher):
    dp.include_router(router)