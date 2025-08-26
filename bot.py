from aiogram import Dispatcher, F, Router, types
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from db import get_user, add_user, get_purchases_count, get_cart_items, DB_PATH
from config import CHANNEL_ID, CHAT_ID, CHANNEL_INVITE, CHAT_INVITE, ADMIN_ID
from aiogram import Bot
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

async def check_subscription(bot: Bot, user_id: int) -> bool:
    """Проверка подписки на канал и чат"""
    try:
        channel_member = await bot.get_chat_member(CHANNEL_ID, user_id)
        chat_member = await bot.get_chat_member(CHAT_ID, user_id)
        return channel_member.status != "left" and chat_member.status != "left"
    except Exception as e:
        logging.error(f"Error checking subscription: {e}")
        return False

def get_main_menu(is_admin: bool = False) -> ReplyKeyboardMarkup:
    """Главное меню"""
    kb = [
        [KeyboardButton(text="Каталог"), KeyboardButton(text="Профиль")],
        [KeyboardButton(text="Корзина"), KeyboardButton(text="Инструкция")]
    ]
    if is_admin:
        kb.append([KeyboardButton(text="Админ-панель")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_subscription_keyboard() -> InlineKeyboardMarkup:
    """Кнопки для подписки"""
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Подписаться на канал", url=CHANNEL_INVITE)],
        [InlineKeyboardButton(text="Подписаться на чат", url=CHAT_INVITE)],
        [InlineKeyboardButton(text="Проверить подписку", callback_data="check_subscription")]
    ])
    return kb

@router.message(CommandStart())
async def start_command(message: Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id
    # Проверка подписки
    if not await check_subscription(bot, user_id):
        await message.answer(
            "Для использования бота подпишись на наш канал и чат!",
            reply_markup=get_subscription_keyboard()
        )
        return
    
    # Регистрация юзера
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
        "Добро пожаловать в магазин арбитража трафика! 🚀",
        reply_markup=get_main_menu(is_admin)
    )
    await state.set_state(UserStates.MAIN_MENU)

@router.callback_query(F.data == "back_to_start")
async def back_to_start(callback: types.CallbackQuery, bot: Bot, state: FSMContext):
    user_id = callback.from_user.id
    if not await check_subscription(bot, user_id):
        await callback.message.edit_text(
            "Для использования бота подпишись на наш канал и чат!",
            reply_markup=get_subscription_keyboard()
        )
        await callback.answer()
    else:
        await callback.message.edit_text(
            "Добро пожаловать в магазин арбитража трафика! 🚀",
            reply_markup=get_main_menu()
        )
        await state.set_state(UserStates.MAIN_MENU)
        await callback.answer()

@router.callback_query(F.data == "check_subscription")
async def check_subscription_callback(callback: types.CallbackQuery, bot: Bot, state: FSMContext):
    user_id = callback.from_user.id
    if await check_subscription(bot, user_id):
        await callback.message.edit_text(
            "Спасибо за подписку! Выбери действие:",
            reply_markup=get_main_menu()
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

@router.callback_query(F.data.startswith("buy_product_"))
async def buy_product(callback: types.CallbackQuery, bot: Bot, state: FSMContext):
    user_id = callback.from_user.id
    if not await check_subscription(bot, user_id):
        await callback.message.edit_text(
            "Подпишись на канал и чат!",
            reply_markup=get_subscription_keyboard()
        )
        await callback.answer()
        return
    
    product_id = int(callback.data.split("_")[-1])
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT id, price FROM products WHERE id = ?", (product_id,))
        product = await cursor.fetchone()
        if product:
            product_id, amount_usd = product
            user = await get_user(user_id)
            discount = user['discount'] if user else 0
            amount_usd = amount_usd * (1 - discount / 100)
            invoice_id = await send_payment_request(bot, user_id, product_id, amount_usd)
            if invoice_id:
                await callback.answer("Платёж создан! Проверь сообщение выше.")
            else:
                await callback.answer("Ошибка при создании платежа.", show_alert=True)
        else:
            await callback.answer("Товар не найден.", show_alert=True)

@router.callback_query(F.data.startswith("pay_item_"))
async def pay_item(callback: types.CallbackQuery, bot: Bot, state: FSMContext):
    user_id = callback.from_user.id
    if not await check_subscription(bot, user_id):
        await callback.message.edit_text(
            "Подпишись на канал и чат!",
            reply_markup=get_subscription_keyboard()
        )
        await callback.answer()
        return
    
    product_id = int(callback.data.split("_")[-1])
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT id, price FROM products WHERE id = ?", (product_id,))
        product = await cursor.fetchone()
        if product:
            product_id, amount_usd = product
            user = await get_user(user_id)
            discount = user['discount'] if user else 0
            amount_usd = amount_usd * (1 - discount / 100)
            invoice_id = await send_payment_request(bot, user_id, product_id, amount_usd)
            if invoice_id:
                await callback.answer("Платёж создан! Проверь сообщение выше.")
                await remove_from_cart(user_id, product_id)  # Удаляем из корзины
            else:
                await callback.answer("Ошибка при создании платежа.", show_alert=True)
        else:
            await callback.answer("Товар не найден.", show_alert=True)

@router.callback_query(F.data.startswith("check_payment_"))
async def check_payment(callback: types.CallbackQuery, bot: Bot, state: FSMContext):
    user_id = callback.from_user.id
    invoice_id = callback.data.split("_")[-1]
    
    if not await check_subscription(bot, user_id):
        await callback.message.edit_text(
            "Подпишись на канал и чат!",
            reply_markup=get_subscription_keyboard()
        )
        await callback.answer()
        return
    
    if await check_invoice(invoice_id):
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT payload FROM invoices WHERE invoice_id = ?", (invoice_id,))
            invoice = await cursor.fetchone()
            if invoice:
                payload = invoice[0].split("_")
                product_id = int(payload[-1]) if payload[-1] != "0" else 0
                is_admin = user_id == ADMIN_ID
                
                if product_id == 0:  # Оплата всей корзины
                    cursor = await db.execute("""
                        SELECT p.id, p.name, p.delivery_file, p.price
                        FROM cart c JOIN products p ON c.product_id = p.id
                        WHERE c.user_id = ?
                    """, (user_id,))
                    cart_items = await cursor.fetchall()
                    if not cart_items:
                        await callback.message.delete()
                        await callback.message.answer(
                            "Корзина пуста или товары не найдены.",
                            reply_markup=get_main_menu(is_admin)
                        )
                        await callback.answer("Ошибка: корзина пуста.", show_alert=True)
                        return
                    
                    text = "Оплата прошла! Ваши товары:\n\n"
                    user = await get_user(user_id)
                    total = 0
                    for item in cart_items:
                        _, name, delivery_file, price = item
                        if user["discount"]:
                            price = price * (1 - user["discount"] / 100)
                        total += price
                        text += f"{name}: {delivery_file}\n"
                        await db.execute(
                            "INSERT INTO orders (user_id, product_id, amount, currency, status) VALUES (?, ?, ?, ?, ?)",
                            (user_id, item[0], price, "USD", "completed")
                        )
                    if user["ref_id"]:
                        ref_earnings = total * 0.1
                        await db.execute(
                            "UPDATE referrals SET earnings = earnings + ? WHERE user_id = ? AND ref_user_id = ?",
                            (ref_earnings, user_id, user["ref_id"])
                        )
                        await db.execute(
                            "UPDATE users SET balance = balance + ? WHERE id = ?",
                            (ref_earnings, user["ref_id"])
                        )
                    await clear_cart(user_id)
                    await db.commit()
                    await bot.send_message(
                        ADMIN_ID,
                        f"Новый заказ! Юзер {user_id} оплатил корзину на {total}$"
                    )
                    await callback.message.delete()
                    await callback.message.answer(text, reply_markup=get_main_menu(is_admin))
                    await callback.answer("Товары выданы!")
                
                else:  # Оплата одного товара
                    cursor = await db.execute(
                        "SELECT delivery_file, price FROM products WHERE id = ?",
                        (product_id,)
                    )
                    product = await cursor.fetchone()
                    if product:
                        delivery_file, price = product
                        user = await get_user(user_id)
                        if user["discount"]:
                            price = price * (1 - user["discount"] / 100)
                        await callback.message.delete()
                        await callback.message.answer(
                            f"Оплата прошла! Твой товар: {delivery_file}",
                            reply_markup=get_main_menu(is_admin)
                        )
                        await db.execute(
                            "INSERT INTO orders (user_id, product_id, amount, currency, status) VALUES (?, ?, ?, ?, ?)",
                            (user_id, product_id, price, "USD", "completed")
                        )
                        if user["ref_id"]:
                            ref_earnings = price * 0.1
                            await db.execute(
                                "UPDATE referrals SET earnings = earnings + ? WHERE user_id = ? AND ref_user_id = ?",
                                (ref_earnings, user_id, user["ref_id"])
                            )
                            await db.execute(
                                "UPDATE users SET balance = balance + ? WHERE id = ?",
                                (ref_earnings, user["ref_id"])
                            )
                        await db.commit()
                        await bot.send_message(
                            ADMIN_ID,
                            f"Новый заказ! Юзер {user_id} купил товар #{product_id} за {price}$"
                        )
                        await callback.answer("Товар выдан!")
                    else:
                        await callback.answer("Товар не найден.", show_alert=True)
            else:
                await callback.answer("Платёж не найден.", show_alert=True)
    else:
        await callback.answer("Оплата ещё не прошла. Попробуй позже.", show_alert=True)

@router.message(Command("catalog"))
@router.message(F.text == "Каталог")
async def catalog_command(message: Message, bot: Bot):
    if not await check_subscription(bot, message.from_user.id):
        await message.answer(
            "Подпишись на канал и чат!",
            reply_markup=get_subscription_keyboard()
        )
        return
    
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT id, name, desc, price, category FROM products")
        products = await cursor.fetchall()
    
    if not products:
        is_admin = message.from_user.id == ADMIN_ID
        await message.answer("Каталог пуст.", reply_markup=get_main_menu(is_admin))
        return
    
    user = await get_user(message.from_user.id)
    discount = user['discount'] if user else 0
    for product in products:
        product_id, name, desc, price, category = product
        final_price = price * (1 - discount / 100)
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"Купить: {final_price}$", callback_data=f"buy_product_{product_id}")],
            [InlineKeyboardButton(text="В корзину", callback_data=f"add_to_cart_{product_id}")]
        ])
        await message.answer(
            f"*{name}*\n\n{desc}\n\nКатегория: {category}\nЦена: {final_price}$",
            reply_markup=kb
        )

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

@router.callback_query(F.data == "back_to_main")
async def back_to_main(callback: types.CallbackQuery, bot: Bot, state: FSMContext):
    user_id = callback.from_user.id
    is_admin = user_id == ADMIN_ID
    await callback.message.delete()
    await callback.message.answer(
        "Добро пожаловать в мощный шоп от DROPZONE! 🚀",
        reply_markup=get_main_menu(is_admin)
    )
    await state.set_state(UserStates.MAIN_MENU)
    await callback.answer()

@router.callback_query(F.data == "referrals_list")
async def referrals_list_command(callback: types.CallbackQuery, bot: Bot, state: FSMContext):
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

def register_handlers(dp: Dispatcher):
    dp.include_router(router)