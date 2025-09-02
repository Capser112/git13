# payments.py
import requests
from config import CRYPTOBOT_TOKEN
import logging
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

async def send_payment_request(bot: Bot, user_id: int, product_id: int, amount_usd: float):
    """Отправить запрос на оплату"""
    url = "https://pay.crypt.bot/api/createInvoice"
    headers = {"Crypto-Pay-API-Token": CRYPTOBOT_TOKEN}
    payload = {
        "amount": str(amount_usd),
        "currency": "USD",
        "asset": "USDT",  # Фиксируем USDT как единственный актив
        "description": f"Покупка товара #{product_id}",
        "payload": f"{user_id}_{product_id}",
        "allowed_assets": ["USDT"]  # Ограничиваем только USDT
    }
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        invoice = response.json()
        if invoice.get("ok"):
            invoice_id = invoice["result"]["invoice_id"]
            payment_url = invoice["result"]["pay_url"]
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Оплатить", url=payment_url)]
            ])
            await bot.send_message(
                user_id,
                f"Оплати {amount_usd}$ за товар #{product_id} в USDT:",
                reply_markup=kb
            )
            return invoice_id
        else:
            logging.error(f"Failed to create invoice: {invoice}")
            return None
    except Exception as e:
        logging.error(f"Error creating invoice: {e}, Response: {response.text if 'response' in locals() else 'No response'}")
        return None

async def check_invoice(invoice_id: str) -> bool:
    """Проверить статус инвойса"""
    url = f"https://pay.crypt.bot/api/getInvoices?invoice_ids={invoice_id}"
    headers = {"Crypto-Pay-API-Token": CRYPTOBOT_TOKEN}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        invoice = response.json()["result"][0]
        return invoice["status"] == "paid"
    except Exception as e:
        logging.error(f"Error checking invoice: {e}")
        return False