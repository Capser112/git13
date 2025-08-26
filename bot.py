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

def get_main_menu() -> ReplyKeyboardMarkup:
    """Главное меню"""
    kb = [
        [KeyboardButton(text="Каталог"), KeyboardButton(text="Профиль")],
        [KeyboardButton(text="Корзина"), KeyboardButton(text="Инструкция")]
    ]
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
    ref_id = message.text.split()[-1] if len(message.text.split()) > 1 else None
    if not await get_user(user_id):
        await add_user(user_id, ref_id)
    
    await message.answer(
        "Добро пожаловать в магазин арбитража трафика! 🚀",
        reply_markup=get_main_menu()
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
            invoice_id = await send_payment_request(bot, user_id, product_id, amount_usd)
            if invoice_id:
                await callback.answer("Платёж создан! Проверь сообщение выше.")
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
        product_id = int(callback.data.split("_")[-2])  # Из payload: user_id_product_id
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT delivery_file, price FROM products WHERE id = ?", (product_id,))
            product = await cursor.fetchone()
            if product:
                delivery_file, price = product
                await callback.message.edit_text(
                    f"Оплата прошла! Твой товар: {delivery_file}",
                    reply_markup=get_main_menu()
                )
                await db.execute(
                    "INSERT INTO orders (user_id, product_id, amount, currency, status) VALUES (?, ?, ?, ?, ?)",
                    (user_id, product_id, price, "USD", "completed")
                )
                await db.commit()
                await bot.send_message(
                    ADMIN_ID,
                    f"Новый заказ! Юзер {user_id} купил товар #{product_id} за {price}$"
                )
        await callback.answer("Товар выдан!")
    else:
        await callback.answer("Оплата ещё не прошла. Попробуй позже.", show_alert=True)

@router.message(Command("catalog"))
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
        await message.answer("Каталог пуст.", reply_markup=get_main_menu())
        return
    
    for product in products:
        product_id, name, desc, price, category = product
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"Купить: {price}$", callback_data=f"buy_product_{product_id}")],
            [InlineKeyboardButton(text="В корзину", callback_data=f"add_to_cart_{product_id}")]
        ])
        await message.answer(
            f"*{name}*\n\n{desc}\n\nКатегория: {category}\nЦена: {price}$",
            reply_markup=kb
        )

@router.message(Command("profile"))
async def profile_command(message: Message, bot: Bot):
    if not await check_subscription(bot, message.from_user.id):
        await message.answer(
            "Подпишись на канал и чат!",
            reply_markup=get_subscription_keyboard()
        )
        return
    
    user = await get_user(message.from_user.id)
    username = message.from_user.username or "Не указан"
    ref_link = f"t.me/{(await bot.get_me()).username}?start=ref_{message.from_user.id}"
    purchases_count = await get_purchases_count(message.from_user.id)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пополнить", callback_data="top_up")],
        [InlineKeyboardButton(text="Корзина", callback_data="cart")],
        [InlineKeyboardButton(text="Ввести промокод", callback_data="enter_promocode")],
        [InlineKeyboardButton(text="История покупок", callback_data="history")],
        [InlineKeyboardButton(text="Назад", callback_data="back_to_main")]
    ])
    await message.answer(
        f"*Профиль*\n\n"
        f"Имя: @{username}\n"
        f"Баланс: {user['balance']}$\n"
        f"Ваша скидка: 0%\n"
        f"Покупок: {purchases_count}\n\n"
        f"Реферальная ссылка: {ref_link}\n"
        f"Рефералов приглашено: {user['referrals_count']}\n"
        f"Заработано на рефералах: {user['earnings']}$",
        reply_markup=kb
    )

@router.message(Command("cart"))
async def cart_command(message: Message, bot: Bot, state: FSMContext):
    if not await check_subscription(bot, message.from_user.id):
        await message.answer(
            "Подпишись на канал и чат!",
            reply_markup=get_subscription_keyboard()
        )
        return
    
    cart_items = await get_cart_items(message.from_user.id)
    if not cart_items:
        await message.answer("Ваша корзина пуста.", reply_markup=get_main_menu())
        return
    
    text = "Ваша корзина:\n\n"
    kb_buttons = []
    for item in cart_items:
        product_id, name, price = item
        text += f"{name} = {price}$\n"
        kb_buttons.append([
            InlineKeyboardButton(text="Оплатить", callback_data=f"pay_item_{product_id}"),
            InlineKeyboardButton(text="Удалить", callback_data=f"delete_item_{product_id}")
        ])
    
    kb_buttons.extend([
        [InlineKeyboardButton(text="Оплатить всю", callback_data="pay_all")],
        [InlineKeyboardButton(text="Очистить всю", callback_data="clear_cart")],
        [InlineKeyboardButton(text="Назад", callback_data="back_to_main")]
    ])
    kb = InlineKeyboardMarkup(inline_keyboard=kb_buttons)
    await message.answer(text, reply_markup=kb)
    await state.set_state(CartStates.VIEW)

@router.message(Command("help"))
async def support_command(message: Message, bot: Bot):
    if not await check_subscription(bot, message.from_user.id):
        await message.answer(
            "Подпишись на канал и чат!",
            reply_markup=get_subscription_keyboard()
        )
        return
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Чат с админом", callback_data="chat_admin")],
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

@router.callback_query(F.data == "back_to_main")
async def back_to_main(callback: types.CallbackQuery, bot: Bot, state: FSMContext):
    await callback.message.edit_text(
        "Добро пожаловать в магазин арбитража трафика! 🚀",
        reply_markup=get_main_menu()
    )
    await state.set_state(UserStates.MAIN_MENU)
    await callback.answer()

def register_handlers(dp: Dispatcher):
    dp.include_router(router)