from aiogram import Router, F, types, Dispatcher
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram import Bot
from config import ADMIN_ID
import aiosqlite
from db import DB_PATH
from bot import get_main_menu

router = Router()

class AdminStates(StatesGroup):
    MAIN = State()
    ADD_PRODUCT_NAME = State()
    ADD_PRODUCT_DESC = State()
    ADD_PRODUCT_PRICE = State()
    ADD_PRODUCT_CATEGORY = State()
    ADD_PRODUCT_FILE = State()

async def admin_command(message: Message, bot: Bot, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Доступ запрещён.")
        return
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Добавить товар", callback_data="add_product")],
        [InlineKeyboardButton(text="Список товаров", callback_data="list_products")],
        [InlineKeyboardButton(text="Промокоды", callback_data="promocodes")],
        [InlineKeyboardButton(text="Скидки", callback_data="discounts")],
        [InlineKeyboardButton(text="Статистика", callback_data="stats")],
        [InlineKeyboardButton(text="Назад", callback_data="back_to_main")]
    ])
    await message.answer("Админ-панель:", reply_markup=kb)
    await state.set_state(AdminStates.MAIN)

async def add_product(callback: types.CallbackQuery, bot: Bot, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Доступ запрещён.", show_alert=True)
        return
    
    await callback.message.edit_text("Введите название товара:")
    await state.set_state(AdminStates.ADD_PRODUCT_NAME)

async def process_product_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Введите описание товара:")
    await state.set_state(AdminStates.ADD_PRODUCT_DESC)

async def process_product_desc(message: Message, state: FSMContext):
    await state.update_data(desc=message.text)
    await message.answer("Введите цену товара (в USD):")
    await state.set_state(AdminStates.ADD_PRODUCT_PRICE)

async def process_product_price(message: Message, state: FSMContext):
    try:
        price = float(message.text)
        if price <= 0:
            raise ValueError
        await state.update_data(price=price)
        await message.answer("Введите категорию (например, Софты/Telegram):")
        await state.set_state(AdminStates.ADD_PRODUCT_CATEGORY)
    except ValueError:
        await message.answer("Цена должна быть числом больше 0. Попробуй снова:")

async def process_product_category(message: Message, state: FSMContext):
    await state.update_data(category=message.text)
    await message.answer("Отправь ссылку или файл для доставки:")
    await state.set_state(AdminStates.ADD_PRODUCT_FILE)

async def process_product_file(message: Message, state: FSMContext):
    data = await state.get_data()
    delivery_file = message.text if message.text else (message.document.file_id if message.document else None)
    if not delivery_file:
        await message.answer("Отправь ссылку или файл:")
        return
    
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO products (name, desc, price, category, delivery_file)
            VALUES (?, ?, ?, ?, ?)
            """,
            (data["name"], data["desc"], data["price"], data["category"], delivery_file)
        )
        await db.commit()
    
    await message.answer("Товар добавлен!", reply_markup=get_main_menu())
    await state.clear()

def register_admin_handlers(dp: Dispatcher):
    dp.include_router(router)