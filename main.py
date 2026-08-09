from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
import sqlite3
import os
import asyncio
import random
import string
from datetime import datetime
from flask import Flask, request
import threading
import logging
import json
import aiohttp

# ============ ЛОГИРОВАНИЕ ============
logging.basicConfig(level=logging.INFO)

# ============ ПЕРЕМЕННЫЕ ============
BOT_TOKEN = "8909837555:AAGZOkg1i3_QoWdpq7PpGu5gJb8-KwIf7WI"
ADMIN_ID = 8901845559
CRYPTOBOT_TOKEN = "620220:A3OkhMfOibpiiWmyYV1194JcNlCwVpkX6p"  # ТОЧНО СО СКРИНШОТА
XROCKET_API_KEY = "64acc4de748ed47a541bb3c47"

# ============ FLASK ДЛЯ WEBHOOKOV ============
app = Flask(__name__)

@app.route('/')
def health():
    return "OK", 200

@app.route('/crypto_webhook', methods=['GET', 'POST'])
def crypto_webhook():
    if request.method == 'GET':
        return "CryptoBot webhook is active", 200
    return "OK", 200

@app.route('/xrocket_webhook', methods=['GET', 'POST'])
def xrocket_webhook():
    if request.method == 'GET':
        return "xRocket webhook is active", 200
    return "OK", 200

# ============ БОТ ============
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

def get_db():
    db_path = os.path.join(os.path.dirname(__file__), "shop.db")
    return sqlite3.connect(db_path)

# ============ КАРТИНКИ ============
IMAGES = {
    "catalog": "AgACAgIAAxkBAANAanjppMpTjWFc4rcQiKkJKjs1DWQAAtQgaxsUCcFLeHo9lHj_7L0BAAMCAAN5AAM9BA",
    "profile": "AgACAgIAAxkBAAMuanjo9MPEBHbsMdTsFMSTRx7HM2QAAtAgaxsUCcFL8OQe0GwLGjoBAAMCAAN5AAM9BA",
    "my_accounts": "AgACAgIAAxkBAAM-anjpa2hL6wfCp6QR7BprJ3hA3ocAAtIgaxsUCcFLOU1dKhM2mk8BAAMCAAN5AAM9BA",
    "deposit": "AgACAgIAAxkBAANGanjp5lUdm-RmUJy_LDeabdZHW5QAAtggaxsUCcFLngPKPQlD9t4BAAMCAAN5AAM9BA",
    "referral": "AgACAgIAAxkBAANEanjp17kCeGj6mhRz-Uv5GBINt5sAAtYgaxsUCcFLnrAluR9mpOgBAAMCAAN5AAM9BA",
    "support": "AgACAgIAAxkBAANKanjqAQxnOuG4UrPN9C2dceRWtMwAAtogaxsUCcFLi3im1mxCbVsBAAMCAAN5AAM9BA",
    "enter_shop": "AgACAgIAAxkBAANCanjpuWbNJLi0IAaU0lAzoey-QloAAtUgaxsUCcFLApfKreEE9AABAQADAgADeQADPQQ",
    "welcome": "AgACAgIAAxkBAANCanjpuWbNJLi0IAaU0lAzoey-QloAAtUgaxsUCcFLApfKreEE9AABAQADAgADeQADPQQ",
}

# ============ ГЕНЕРАЦИЯ РЕФЕРАЛЬНОГО КОДА ============
def generate_ref_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

def get_or_create_ref_code(user_id):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT ref_code FROM users WHERE id = ?", (user_id,))
    result = cursor.fetchone()
    db.close()
    
    if result and result[0]:
        return result[0]
    else:
        new_code = generate_ref_code()
        db = get_db()
        cursor = db.cursor()
        cursor.execute("UPDATE users SET ref_code = ? WHERE id = ?", (new_code, user_id))
        db.commit()
        db.close()
        return new_code

async def apply_referral(new_user_id, ref_code):
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute("SELECT id FROM users WHERE ref_code = ?", (ref_code,))
    result = cursor.fetchone()
    
    if result:
        referrer_id = result[0]
        cursor.execute("UPDATE users SET referrer_id = ? WHERE id = ?", (referrer_id, new_user_id))
        BONUS_AMOUNT = 10
        cursor.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (BONUS_AMOUNT, referrer_id))
        cursor.execute("UPDATE users SET ref_bonus = ref_bonus + ? WHERE id = ?", (BONUS_AMOUNT, referrer_id))
        db.commit()
        db.close()
        
        try:
            await bot.send_message(
                referrer_id,
                f"🎉 *Кто-то перешёл по вашей реферальной ссылке!*\n\n"
                f"💰 Вы получили бонус: +{BONUS_AMOUNT} ₽\n"
                f"📊 Ваш баланс пополнен!\n"
                f"🌟 Спасибо, что приглашаете друзей!",
                parse_mode="Markdown"
            )
        except:
            pass
        
        return True, BONUS_AMOUNT
    
    db.close()
    return False, 0

# ============ КРИПТОПЛАТЕЖИ ============
async def create_cryptobot_invoice(user_id, amount_usd):
    try:
        url = "https://pay.crypt.bot/v1/invoice/create"
        payload = {
            "currency_type": "fiat",
            "fiat": "USD",
            "amount": str(amount_usd),
            "description": f"Пополнение баланса OksiShop",
            "payload": f"user_{user_id}",
            "expires_in": 3600
        }
        headers = {
            "Authorization": f"Bearer {CRYPTOBOT_TOKEN}",
            "Content-Type": "application/json"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as resp:
                data = await resp.json()
                logging.info(f"CryptoBot create response: {data}")
                if data.get("status") == "success":
                    invoice = data.get("result")
                    return {
                        "success": True,
                        "invoice_id": invoice.get("invoice_id"),
                        "pay_url": invoice.get("bot_invoice_url"),
                        "amount": amount_usd
                    }
                else:
                    return {"success": False, "error": data.get("error", "Unknown error")}
    except Exception as e:
        logging.error(f"CryptoBot error: {e}")
        return {"success": False, "error": str(e)}

async def check_cryptobot_payment(invoice_id):
    try:
        url = f"https://pay.crypt.bot/v1/invoice/get?invoice_id={invoice_id}"
        headers = {
            "Authorization": f"Bearer {CRYPTOBOT_TOKEN}",
            "Content-Type": "application/json"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                data = await resp.json()
                if data.get("status") == "success":
                    invoice = data.get("result")
                    if invoice.get("status") == "paid":
                        return {
                            "success": True, 
                            "paid": True, 
                            "amount": float(invoice.get("amount"))
                        }
                    else:
                        return {
                            "success": True, 
                            "paid": False, 
                            "status": invoice.get("status")
                        }
                else:
                    return {"success": False, "error": data.get("error", "Unknown error")}
    except Exception as e:
        logging.error(f"CryptoBot check error: {e}")
        return {"success": False, "error": str(e)}

# ============ XROCKET ============
async def create_xrocket_invoice(user_id, amount_usd):
    try:
        amount_ton = amount_usd / 5.0
        
        url = "https://pay.xrocket.tg/invoice"
        headers = {
            "Rocket-Pay-Key": XROCKET_API_KEY,
            "Content-Type": "application/json"
        }
        payload = {
            "currency": "TON",
            "amount": str(round(amount_ton, 2)),
            "description": f"Пополнение баланса OksiShop",
            "expiresIn": 3600
        }
        
        logging.info(f"📤 xRocket запрос: {payload}")
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as resp:
                data = await resp.json()
                logging.info(f"📥 xRocket ответ: {data}")
                
                if data.get("status") == "success":
                    invoice = data.get("data", {})
                    return {
                        "success": True,
                        "invoice_id": invoice.get("invoiceId"),
                        "pay_url": invoice.get("link"),
                        "amount": amount_usd
                    }
                else:
                    return {"success": False, "error": data.get("error", "Unknown error")}
    except Exception as e:
        logging.error(f"xRocket error: {e}")
        return {"success": False, "error": str(e)}

# ============ ГЛАВНОЕ МЕНЮ ============
def main_menu():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📦 Каталог товаров", callback_data="catalog")],
        [InlineKeyboardButton(text="👤 Мой профиль", callback_data="profile")],
        [InlineKeyboardButton(text="📱 Мои покупки", callback_data="my_accounts")],
        [InlineKeyboardButton(text="💰 Пополнить баланс", callback_data="deposit")],
        [InlineKeyboardButton(text="🎁 Реферальная система", callback_data="referral")],
        [InlineKeyboardButton(text="🛠 Техподдержка", callback_data="support")],
        [InlineKeyboardButton(text="❓ Помощь и FAQ", callback_data="help")]
    ])
    return keyboard

def back_button():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_to_menu")]
    ])

# ============ ОБРАБОТЧИКИ КНОПОК ============
@dp.message(Command("start"))
async def start(message: Message):
    user_id = message.from_user.id
    
    args = message.text.split()
    ref_code = None
    if len(args) > 1:
        ref_code = args[1]
    
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute("SELECT id FROM users WHERE id = ?", (user_id,))
    existing_user = cursor.fetchone()
    
    if not existing_user:
        join_date = datetime.now().strftime("%d.%m.%Y %H:%M")
        
        cursor.execute(
            "INSERT INTO users (id, balance, join_date) VALUES (?, 0, ?)",
            (user_id, join_date)
        )
        db.commit()
        
        if ref_code:
            success, bonus = await apply_referral(user_id, ref_code)
            if success:
                bonus_text = f"\n🎉 Вы активировали реферальный код!\n💰 Бонус +{bonus} ₽ на счёт пригласившего!"
            else:
                bonus_text = "\n❌ Неверный реферальный код"
        else:
            bonus_text = ""
        
        db.close()
        
        welcome_text = f"""
🌟 *ДОБРО ПОЖАЛОВАТЬ В OksiShop!* 🌟
{bonus_text}

🔥 *Лучшие аккаунты по лучшим ценам!*

👇 *Нажми на кнопку ниже, чтобы начать!*
        """
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🛒 За покупками!", callback_data="enter_shop")],
            [InlineKeyboardButton(text="❓ Что это?", callback_data="help")]
        ])
        
        await message.answer_photo(
            photo=IMAGES["welcome"],
            caption=welcome_text,
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    else:
        db.close()
        
        welcome_back_text = """
🌟 *ДОБРО ПОЖАЛОВАТЬ ОБРАТНО В OksiShop!* 🌟

👇 *Выберите действие в меню:*
        """
        
        await message.answer_photo(
            photo=IMAGES["welcome"],
            caption=welcome_back_text,
            parse_mode="Markdown",
            reply_markup=main_menu()
        )

@dp.callback_query(lambda c: c.data == "enter_shop")
async def enter_shop(callback: CallbackQuery):
    try:
        await callback.answer()
    except:
        pass
    
    shop_text = """
🛍️ *ДОБРО ПОЖАЛОВАТЬ В МАГАЗИН!* 🛍️

Выберите действие в меню ниже 👇

━━━━━━━━━━━━━━━━━━━
📦 *Каталог* — посмотреть ассортимент
👤 *Профиль* — проверить баланс
📱 *Мои покупки* — история покупок
💰 *Пополнить* — пополнить баланс криптой
🎁 *Рефералка* — приглашай друзей
🛠 *Поддержка* — помощь и контакты
❓ *Помощь* — ответы на вопросы
━━━━━━━━━━━━━━━━━━━
"""
    
    await callback.message.delete()
    await callback.message.answer_photo(
        photo=IMAGES["enter_shop"],
        caption=shop_text,
        parse_mode="Markdown",
        reply_markup=main_menu()
    )

@dp.callback_query(lambda c: c.data == "catalog")
async def show_catalog(callback: CallbackQuery):
    try:
        await callback.answer()
    except:
        pass
    
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute("PRAGMA table_info(products)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if "image" in columns:
        cursor.execute("SELECT id, name, price, stock, image FROM products WHERE stock > 0")
        products = cursor.fetchall()
    else:
        cursor.execute("SELECT id, name, price, stock FROM products WHERE stock > 0")
        products = [(p[0], p[1], p[2], p[3], None) for p in cursor.fetchall()]
    db.close()
    
    if not products:
        await callback.message.delete()
        await callback.message.answer_photo(
            photo=IMAGES["catalog"],
            caption="😔 *К сожалению, товаров нет в наличии!*\n\n🔄 Загляните позже — мы постоянно обновляем ассортимент!",
            parse_mode="Markdown",
            reply_markup=back_button()
        )
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for p in products:
        product_id, name, price, stock, image = p
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(
                text=f"📌 {name} — {price} ₽ (осталось: {stock})",
                callback_data=f"view_{product_id}"
            )
        ])
    keyboard.inline_keyboard.append([InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_to_menu")])
    
    caption = """
📦 *КАТАЛОГ ТОВАРОВ* 📦

👇 *Нажмите на товар, чтобы посмотреть подробности:*
"""
    
    await callback.message.delete()
    await callback.message.answer_photo(
        photo=IMAGES["catalog"],
        caption=caption,
        parse_mode="Markdown",
        reply_markup=keyboard
    )

@dp.callback_query(lambda c: c.data and c.data.startswith("view_"))
async def view_product(callback: CallbackQuery):
    try:
        await callback.answer()
    except:
        pass
    
    product_id = int(callback.data.split("_")[1])
    
    db = get_db()
    cursor = db.cursor()
    cursor.execute("PRAGMA table_info(products)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if "image" in columns:
        cursor.execute("SELECT id, name, price, stock, image FROM products WHERE id = ?", (product_id,))
        product = cursor.fetchone()
    else:
        cursor.execute("SELECT id, name, price, stock FROM products WHERE id = ?", (product_id,))
        p = cursor.fetchone()
        product = (p[0], p[1], p[2], p[3], None) if p else None
    db.close()
    
    if not product:
        await callback.message.edit_text(
            "❌ Товар не найден",
            reply_markup=back_button()
        )
        return
    
    product_id, name, price, stock, image = product
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 Купить сейчас", callback_data=f"buy_{product_id}")],
        [InlineKeyboardButton(text="🔙 Назад в каталог", callback_data="catalog")]
    ])
    
    caption = f"""
*{name}* 🎯

💰 *Цена:* {price} ₽
📊 *В наличии:* {stock} шт.

📌 *Описание:*
✅ Живой аккаунт
✅ Готов к использованию
✅ Гарантия 1 час

👇 *Нажми «Купить», чтобы приобрести!*
"""
    
    if image:
        await callback.message.delete()
        await callback.message.answer_photo(
            photo=image,
            caption=caption,
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    else:
        await callback.message.edit_text(
            caption,
            parse_mode="Markdown",
            reply_markup=keyboard
        )

@dp.callback_query(lambda c: c.data and c.data.startswith("buy_"))
async def buy_product(callback: CallbackQuery):
    try:
        await callback.answer()
    except:
        pass
    
    product_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute("SELECT balance FROM users WHERE id = ?", (user_id,))
    balance = cursor.fetchone()[0]
    
    cursor.execute("SELECT price, name, stock FROM products WHERE id = ?", (product_id,))
    price, name, stock = cursor.fetchone()
    
    if balance < price:
        await callback.message.edit_text(
            f"❌ *НЕДОСТАТОЧНО СРЕДСТВ!* ❌\n\n"
            f"📌 Товар: {name}\n"
            f"💰 Цена: {price} ₽\n"
            f"💳 Ваш баланс: {balance} ₽\n"
            f"📊 Не хватает: {price - balance} ₽\n\n"
            f"💰 Пополните баланс в главном меню!",
            parse_mode="Markdown",
            reply_markup=back_button()
        )
        db.close()
        return
    
    cursor.execute("SELECT id, data FROM accounts WHERE product_id = ? AND status = 'available' LIMIT 1", (product_id,))
    acc = cursor.fetchone()
    
    if not acc:
        await callback.message.edit_text(
            "😔 *Аккаунты закончились!*\n\n"
            "🔄 Загляните позже — мы пополняем запасы каждый день!",
            parse_mode="Markdown",
            reply_markup=back_button()
        )
        db.close()
        return
    
    acc_id, acc_data = acc
    
    cursor.execute("UPDATE users SET balance = balance - ? WHERE id = ?", (price, user_id))
    cursor.execute("UPDATE accounts SET status = 'sold', buyer_id = ?, buy_date = ? WHERE id = ?", 
                   (user_id, datetime.now().strftime("%d.%m.%Y %H:%M"), acc_id))
    db.commit()
    db.close()
    
    await callback.message.edit_text(
        f"✅ *ПОКУПКА УСПЕШНА!* ✅\n\n"
        f"📌 Товар: {name}\n"
        f"💰 Списано: {price} ₽\n"
        f"⏰ Время покупки: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
        f"📝 *Данные аккаунта:*\n"
        f"`{acc_data}`\n\n"
        f"⚠️ *ВАЖНО:*\n"
        f"⏳ Гарантия 1 час с момента получения\n"
        f"🔒 Проверьте данные сразу!\n"
        f"📩 При проблемах пишите: @YoungTrappa8122\n\n"
        f"🌟 Спасибо за покупку! Ждём вас снова!",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📦 В каталог", callback_data="catalog")],
            [InlineKeyboardButton(text="🏠 В меню", callback_data="back_to_menu")]
        ])
    )

@dp.callback_query(lambda c: c.data == "profile")
async def show_profile(callback: CallbackQuery):
    try:
        await callback.answer()
    except:
        pass
    
    user_id = callback.from_user.id
    username = f"@{callback.from_user.username}" if callback.from_user.username else "не указан"
    
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT balance, join_date FROM users WHERE id = ?", (user_id,))
    result = cursor.fetchone()
    if result:
        balance, join_date = result
    else:
        balance, join_date = 0, "Неизвестно"
    db.close()
    
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT COUNT(*) FROM accounts WHERE status = 'sold' AND buyer_id = ?", (user_id,))
    total_bought = cursor.fetchone()[0]
    db.close()
    
    db = get_db()
    cursor = db.cursor()
    cursor.execute("""
        SELECT SUM(p.price) 
        FROM accounts a 
        JOIN products p ON a.product_id = p.id 
        WHERE a.status = 'sold' AND a.buyer_id = ?
    """, (user_id,))
    total_spent = cursor.fetchone()[0] or 0
    db.close()
    
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT COUNT(*) FROM users WHERE referrer_id = ?", (user_id,))
    referrals = cursor.fetchone()[0]
    cursor.execute("SELECT ref_bonus FROM users WHERE id = ?", (user_id,))
    ref_bonus = cursor.fetchone()[0] or 0
    db.close()
    
    caption = f"""
👤 *МОЙ ПРОФИЛЬ* 👤
━━━━━━━━━━━━━━━━━━━

👤 *Имя:* {callback.from_user.full_name}
🆔 *Юзернейм:* {username}
📅 *Дата регистрации:* {join_date}

━━━━━━━━━━━━━━━━━━━
💰 *БАЛАНС:* {balance} ₽
━━━━━━━━━━━━━━━━━━━

📊 *СТАТИСТИКА:*
📦 Куплено аккаунтов: {total_bought}
💳 Потрачено всего: {total_spent} ₽
👥 Приглашено друзей: {referrals}
🎁 Заработано с рефералов: {ref_bonus} ₽

━━━━━━━━━━━━━━━━━━━

🌟 *Статус:* 
{"👑 VIP клиент!" if total_spent >= 500 else "🆕 Новый клиент" if total_bought == 0 else "💎 Постоянный клиент"}

📩 По вопросам: @YoungTrappa8122
"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Пополнить баланс", callback_data="deposit")],
        [InlineKeyboardButton(text="📱 Мои покупки", callback_data="my_accounts")],
        [InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_to_menu")]
    ])
    
    await callback.message.delete()
    await callback.message.answer_photo(
        photo=IMAGES["profile"],
        caption=caption,
        parse_mode="Markdown",
        reply_markup=keyboard
    )

@dp.callback_query(lambda c: c.data == "my_accounts")
async def show_my_accounts(callback: CallbackQuery):
    try:
        await callback.answer()
    except:
        pass
    
    user_id = callback.from_user.id
    
    db = get_db()
    cursor = db.cursor()
    cursor.execute("""
        SELECT p.name, a.data, a.buy_date, p.price
        FROM accounts a 
        JOIN products p ON a.product_id = p.id 
        WHERE a.status = 'sold' AND a.buyer_id = ?
        ORDER BY a.id DESC 
        LIMIT 10
    """, (user_id,))
    accounts = cursor.fetchall()
    db.close()
    
    if not accounts:
        await callback.message.delete()
        await callback.message.answer_photo(
            photo=IMAGES["my_accounts"],
            caption="📭 *У вас пока нет купленных аккаунтов!*\n\n🛒 Перейдите в раздел «Каталог» и сделайте свою первую покупку! 🚀",
            parse_mode="Markdown",
            reply_markup=back_button()
        )
        return
    
    text = "📱 *МОИ ПОКУПКИ* 📱\n"
    text += "━━━━━━━━━━━━━━━━━━━\n"
    text += f"📊 Всего: {len(accounts)} (последние 10)\n\n"
    
    for idx, acc in enumerate(accounts, 1):
        text += f"🔹 *{idx}. {acc[0]}*\n"
        text += f"📝 Данные: `{acc[1]}`\n"
        text += f"💰 Цена: {acc[3]} ₽\n"
        text += f"⏰ Куплен: {acc[2]}\n\n"
    
    text += "━━━━━━━━━━━━━━━━━━━\n"
    text += "⚠️ *Напоминание:*\n"
    text += "⏳ Гарантия 1 час с момента покупки\n"
    text += "📩 При проблемах: @YoungTrappa8122"
    
    keyboard = back_button()
    
    await callback.message.delete()
    await callback.message.answer_photo(
        photo=IMAGES["my_accounts"],
        caption=text,
        parse_mode="Markdown",
        reply_markup=keyboard
    )

@dp.callback_query(lambda c: c.data == "deposit")
async def show_deposit(callback: CallbackQuery):
    try:
        await callback.answer()
    except:
        pass
    
    caption = """
💰 *ПОПОЛНЕНИЕ БАЛАНСА* 💰
━━━━━━━━━━━━━━━━━━━

Выберите способ пополнения:

💳 *CryptoBot* — быстрая оплата в криптовалюте
🚀 *xRocket* — оплата через TON

👇 *Нажмите на кнопку ниже, чтобы выбрать способ:*
"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 CryptoBot", callback_data="deposit_cryptobot")],
        [InlineKeyboardButton(text="🚀 xRocket", callback_data="deposit_xrocket")],
        [InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_to_menu")]
    ])
    
    await callback.message.delete()
    await callback.message.answer_photo(
        photo=IMAGES["deposit"],
        caption=caption,
        parse_mode="Markdown",
        reply_markup=keyboard
    )

@dp.callback_query(lambda c: c.data == "deposit_cryptobot")
async def deposit_cryptobot(callback: CallbackQuery):
    try:
        await callback.answer()
    except:
        pass
    
    await callback.message.delete()
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 10 ₽", callback_data="cb_amount_10")],
        [InlineKeyboardButton(text="💰 50 ₽", callback_data="cb_amount_50")],
        [InlineKeyboardButton(text="💰 100 ₽", callback_data="cb_amount_100")],
        [InlineKeyboardButton(text="💰 500 ₽", callback_data="cb_amount_500")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="deposit")]
    ])
    
    await callback.message.answer(
        "💰 *CryptoBot — выберите сумму пополнения:*\n\n"
        "Минимальная сумма: 10 ₽",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

@dp.callback_query(lambda c: c.data and c.data.startswith("cb_amount_"))
async def process_cryptobot_amount(callback: CallbackQuery):
    try:
        await callback.answer()
    except:
        pass
    
    amount_rub = float(callback.data.split("_")[2])
    amount_usd = amount_rub / 100
    user_id = callback.from_user.id
    
    result = await create_cryptobot_invoice(user_id, amount_usd)
    
    if not result["success"]:
        await callback.message.edit_text(
            f"❌ *Ошибка создания счета:*\n{result['error']}\n\n"
            "Попробуйте позже.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="deposit")]
            ])
        )
        return
    
    await callback.message.edit_text(
        f"✅ *Счёт создан!* ✅\n\n"
        f"💰 Сумма: {amount_rub} ₽\n"
        f"🔗 *Ссылка для оплаты:*\n"
        f"{result['pay_url']}\n\n"
        f"📌 После оплаты нажмите «Проверить оплату»",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Проверить оплату", callback_data=f"check_cb_{result['invoice_id']}")],
            [InlineKeyboardButton(text="🏠 В меню", callback_data="back_to_menu")]
        ])
    )

@dp.callback_query(lambda c: c.data and c.data.startswith("check_cb_"))
async def check_cryptobot_payment_handler(callback: CallbackQuery):
    try:
        await callback.answer()
    except:
        pass
    
    invoice_id = callback.data.split("_")[2]
    user_id = callback.from_user.id
    
    result = await check_cryptobot_payment(invoice_id)
    
    if not result["success"]:
        await callback.message.edit_text(
            f"❌ Ошибка проверки: {result['error']}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data=f"check_cb_{invoice_id}")],
                [InlineKeyboardButton(text="🏠 В меню", callback_data="back_to_menu")]
            ])
        )
        return
    
    if result["paid"]:
        db = get_db()
        cursor = db.cursor()
        amount_rub = int(result["amount"] * 100)
        cursor.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (amount_rub, user_id))
        db.commit()
        db.close()
        
        await callback.message.edit_text(
            f"✅ *Оплата подтверждена!* ✅\n\n"
            f"💰 Начислено: {amount_rub} ₽\n"
            f"📊 Проверьте баланс в профиле!\n"
            f"🌟 Спасибо за пополнение!",
            parse_mode="Markdown",
            reply_markup=main_menu()
        )
    else:
        await callback.message.edit_text(
            f"⏳ *Оплата ещё не подтверждена*\n\n"
            f"Подождите 1-2 минуты и попробуйте снова.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Проверить снова", callback_data=f"check_cb_{invoice_id}")],
                [InlineKeyboardButton(text="🏠 В меню", callback_data="back_to_menu")]
            ])
        )

@dp.callback_query(lambda c: c.data == "deposit_xrocket")
async def deposit_xrocket(callback: CallbackQuery):
    try:
        await callback.answer()
    except:
        pass
    
    await callback.message.delete()
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 10 ₽", callback_data="xr_amount_10")],
        [InlineKeyboardButton(text="🚀 50 ₽", callback_data="xr_amount_50")],
        [InlineKeyboardButton(text="🚀 100 ₽", callback_data="xr_amount_100")],
        [InlineKeyboardButton(text="🚀 500 ₽", callback_data="xr_amount_500")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="deposit")]
    ])
    
    await callback.message.answer(
        "🚀 *xRocket — выберите сумму пополнения:*\n\n"
        "Минимальная сумма: 10 ₽\n"
        "Оплата в TON (1 TON ≈ 5 USD)",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

@dp.callback_query(lambda c: c.data and c.data.startswith("xr_amount_"))
async def process_xrocket_amount(callback: CallbackQuery):
    try:
        await callback.answer()
    except:
        pass
    
    amount_rub = float(callback.data.split("_")[2])
    amount_usd = amount_rub / 100
    user_id = callback.from_user.id
    
    result = await create_xrocket_invoice(user_id, amount_usd)
    
    if not result["success"]:
        await callback.message.edit_text(
            f"❌ *Ошибка создания счета:*\n{result['error']}\n\n"
            "Попробуйте позже.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="deposit")]
            ])
        )
        return
    
    await callback.message.edit_text(
        f"✅ *Счёт создан!* ✅\n\n"
        f"💰 Сумма: {amount_rub} ₽\n"
        f"🔗 *Ссылка для оплаты:*\n"
        f"{result['pay_url']}\n\n"
        f"📌 После оплаты нажмите «Проверить оплату»",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Проверить оплату", callback_data=f"check_xr_{result['invoice_id']}")],
            [InlineKeyboardButton(text="🏠 В меню", callback_data="back_to_menu")]
        ])
    )

@dp.callback_query(lambda c: c.data and c.data.startswith("check_xr_"))
async def check_xrocket_payment_handler(callback: CallbackQuery):
    try:
        await callback.answer()
    except:
        pass
    
    await callback.message.edit_text(
        "⏳ *Проверка оплаты...*\n\n"
        "Функция автоматической проверки для xRocket в разработке.\n"
        "Пожалуйста, свяжитесь с админом для ручного пополнения: @YoungTrappa8122",
        parse_mode="Markdown",
        reply_markup=back_button()
    )

@dp.callback_query(lambda c: c.data == "referral")
async def show_referral(callback: CallbackQuery):
    try:
        await callback.answer()
    except:
        pass
    
    user_id = callback.from_user.id
    ref_code = get_or_create_ref_code(user_id)
    
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT COUNT(*) FROM users WHERE referrer_id = ?", (user_id,))
    referrals_count = cursor.fetchone()[0]
    cursor.execute("SELECT ref_bonus FROM users WHERE id = ?", (user_id,))
    ref_bonus = cursor.fetchone()[0] or 0
    db.close()
    
    bot_username = "Oksitocin_Shop_Bot"
    ref_link = f"https://t.me/{bot_username}?start={ref_code}"
    
    caption = f"""
🎁 *РЕФЕРАЛЬНАЯ СИСТЕМА* 🎁
━━━━━━━━━━━━━━━━━━━

👥 *Приглашайте друзей и получайте бонусы!*

💰 *Бонус за приглашение:* 10 ₽

📊 *Ваша статистика:*
👤 Приглашено: {referrals_count} чел.
💰 Заработано: {ref_bonus} ₽
🔑 Ваш код: `{ref_code}`

🔗 *Ваша реферальная ссылка:*
`{ref_link}`

📌 *Как это работает:*
1️⃣ Отправьте ссылку другу
2️⃣ Он переходит и регистрируется
3️⃣ Вы получаете 10 ₽ на баланс!
"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Скопировать ссылку", callback_data=f"copy_ref_{ref_code}")],
        [InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_to_menu")]
    ])
    
    await callback.message.delete()
    await callback.message.answer_photo(
        photo=IMAGES["referral"],
        caption=caption,
        parse_mode="Markdown",
        reply_markup=keyboard
    )

@dp.callback_query(lambda c: c.data and c.data.startswith("copy_ref_"))
async def copy_referral(callback: CallbackQuery):
    try:
        await callback.answer()
    except:
        pass
    
    ref_code = callback.data.split("_")[2]
    bot_username = "Oksitocin_Shop_Bot"
    ref_link = f"https://t.me/{bot_username}?start={ref_code}"
    
    await callback.message.answer(
        f"🔗 *Ваша реферальная ссылка:*\n\n"
        f"`{ref_link}`\n\n"
        f"📋 Нажмите на ссылку, чтобы скопировать её.",
        parse_mode="Markdown"
    )
    await callback.answer("Ссылка отправлена!")

@dp.callback_query(lambda c: c.data == "support")
async def show_support(callback: CallbackQuery):
    try:
        await callback.answer()
    except:
        pass
    
    caption = """
🛠 *ТЕХНИЧЕСКАЯ ПОДДЕРЖКА* 🛠
━━━━━━━━━━━━━━━━━━━

📩 *Связь:* @YoungTrappa8122
⏰ *Время ответа:* 5-15 минут
"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📩 Связаться", url="https://t.me/YoungTrappa8122")],
        [InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_to_menu")]
    ])
    
    await callback.message.delete()
    await callback.message.answer_photo(
        photo=IMAGES["support"],
        caption=caption,
        parse_mode="Markdown",
        reply_markup=keyboard
    )

@dp.callback_query(lambda c: c.data == "help")
async def show_help(callback: CallbackQuery):
    try:
        await callback.answer()
    except:
        pass
    
    help_text = """
❓ *ПОМОЩЬ И FAQ* ❓
━━━━━━━━━━━━━━━━━━━

📌 *КАК КУПИТЬ АККАУНТ:*

1️⃣ *Пополните баланс* через CryptoBot или xRocket
2️⃣ *Выберите товар* в каталоге
3️⃣ *Нажмите «Купить»* — данные придут сразу!

━━━━━━━━━━━━━━━━━━━

⏳ *ГАРАНТИЯ:* 1 час на проверку
📩 *ПОДДЕРЖКА:* @YoungTrappa8122
"""
    
    await callback.message.delete()
    await callback.message.answer(
        help_text,
        parse_mode="Markdown",
        reply_markup=back_button()
    )

@dp.callback_query(lambda c: c.data == "back_to_menu")
async def back_to_menu(callback: CallbackQuery):
    try:
        await callback.answer()
    except:
        pass
    
    await callback.message.delete()
    await callback.message.answer(
        "🌟 *ГЛАВНОЕ МЕНЮ* 🌟\n\n"
        "👇 *Выберите действие:*",
        parse_mode="Markdown",
        reply_markup=main_menu()
    )

@dp.message(Command("add"))
async def add_balance(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Доступ запрещен")
        return
    
    try:
        parts = message.text.split()
        user_id = int(parts[1])
        amount = int(parts[2])
    except:
        await message.answer("❌ Формат: /add [user_id] [сумма]")
        return
    
    db = get_db()
    cursor = db.cursor()
    cursor.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (amount, user_id))
    db.commit()
    db.close()
    
    await message.answer(f"✅ Баланс пользователя {user_id} пополнен на {amount} ₽")

@dp.message(Command("getid"))
async def get_file_id(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    if message.photo:
        file_id = message.photo[-1].file_id
        await message.answer(f"📸 File ID:\n`{file_id}`", parse_mode="Markdown")
    elif message.document:
        file_id = message.document.file_id
        await message.answer(f"📄 File ID:\n`{file_id}`", parse_mode="Markdown")
    else:
        await message.answer("❌ Отправьте картинку или файл, а затем напишите /getid")

# ============ ЗАПУСК ============
async def main():
    print("🤖 Бот запущен и готов к работе!")
    print(f"👤 Админ ID: {ADMIN_ID}")
    print(f"📩 Юзернейм админа: @YoungTrappa8122")
    print("✅ Ожидание сообщений...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    threading.Thread(
        target=lambda: app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False),
        daemon=True
    ).start()
    print(f"✅ Flask сервер запущен на порту {port}")
    
    asyncio.run(main())
