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
CRYPTOBOT_TOKEN = "620260:AAPBw2V0DulWNwGOmKInLH926esMEySWgqa"
XROCKET_API_KEY = "64acc4de748ed47a541bb3c47"

# ============ FLASK ДЛЯ WEBHOOK ============
app = Flask(__name__)

@app.route('/')
def health():
    return "OK", 200

@app.route('/crypto_webhook', methods=['GET', 'POST'])
def crypto_webhook():
    if request.method == 'GET':
        return "✅ CryptoBot webhook is active", 200
    
    try:
        data = request.get_json()
        logging.info(f"📩 Получен вебхук от CryptoBot: {data}")
        
        if data and data.get('update_type') == 'invoice_paid':
            payload = data.get('payload', {})
            user_id_str = payload.get('payload', '')
            
            if user_id_str.startswith('user_'):
                user_id = int(user_id_str.split('_')[1])
                amount_usd = float(payload.get('amount', 0))
                amount_rub = int(amount_usd * 100)
                
                db = get_db()
                cursor = db.cursor()
                cursor.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (amount_rub, user_id))
                db.commit()
                db.close()
                
                logging.info(f"✅ Начислено {amount_rub} ₽ пользователю {user_id}")
                
                # Отправляем уведомление пользователю через asyncio
                try:
                    asyncio.run_coroutine_threadsafe(
                        bot.send_message(
                            user_id,
                            f"✅ *Оплата подтверждена!* ✅\n\n"
                            f"💰 Начислено: {amount_rub} ₽\n"
                            f"📊 Проверьте баланс в профиле!\n"
                            f"🌟 Спасибо за пополнение!",
                            parse_mode="Markdown"
                        ),
                        asyncio.get_event_loop()
                    )
                except:
                    pass
                
                return "OK", 200
        
        return "OK", 200
    except Exception as e:
        logging.error(f"CryptoBot webhook error: {e}")
        return "Error", 500

@app.route('/xrocket_webhook', methods=['GET', 'POST'])
def xrocket_webhook():
    if request.method == 'GET':
        return "✅ xRocket webhook is active", 200
    
    try:
        data = request.get_json()
        logging.info(f"📩 Получен вебхук от xRocket: {data}")
        
        if data and data.get('status') == 'success':
            invoice_data = data.get('data', {})
            invoice_id = invoice_data.get('invoiceId')
            
            if invoice_id:
                db = get_db()
                cursor = db.cursor()
                cursor.execute("SELECT user_id, amount FROM pending_payments WHERE invoice_id = ? AND system = 'xrocket'", (invoice_id,))
                result = cursor.fetchone()
                
                if result:
                    user_id, amount_usd = result
                    amount_rub = int(amount_usd * 100)
                    
                    cursor.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (amount_rub, user_id))
                    cursor.execute("UPDATE pending_payments SET status = 'paid' WHERE invoice_id = ?", (invoice_id,))
                    db.commit()
                    db.close()
                    
                    logging.info(f"✅ xRocket: начислено {amount_rub} ₽ пользователю {user_id}")
                    
                    try:
                        asyncio.run_coroutine_threadsafe(
                            bot.send_message(
                                user_id,
                                f"✅ *Оплата подтверждена!* ✅\n\n"
                                f"💰 Начислено: {amount_rub} ₽\n"
                                f"🚀 Спасибо за пополнение через xRocket!",
                                parse_mode="Markdown"
                            ),
                            asyncio.get_event_loop()
                        )
                    except:
                        pass
                    
                    return "OK", 200
                db.close()
        return "OK", 200
    except Exception as e:
        logging.error(f"xRocket webhook error: {e}")
        return "Error", 500

# ============ БОТ ============
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

def get_db():
    db_path = os.path.join(os.path.dirname(__file__), "shop.db")
    
    db = sqlite3.connect(db_path)
    cursor = db.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            balance INTEGER DEFAULT 0,
            join_date TEXT,
            username TEXT
        )
    ''')
    
    cursor.execute("PRAGMA table_info(users)")
    columns = [col[1] for col in cursor.fetchall()]
    if "username" not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN username TEXT")
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            price INTEGER,
            stock INTEGER,
            image TEXT,
            category TEXT DEFAULT 'accounts'
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER,
            data TEXT,
            proxy TEXT,
            status TEXT DEFAULT 'available',
            buyer_id INTEGER,
            buy_date TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pending_payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            invoice_id TEXT,
            amount REAL,
            system TEXT,
            created_at TEXT,
            status TEXT DEFAULT 'pending'
        )
    ''')
    
    db.commit()
    db.close()
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

# ============ CRYPTOBOT ============
async def create_cryptobot_invoice(user_id, amount_usd):
    try:
        url = "https://pay.crypt.bot/api/createInvoice"
        payload = {
            "currency_type": "fiat",
            "fiat": "USD",
            "amount": str(amount_usd),
            "description": f"Пополнение баланса OksiShop",
            "payload": f"user_{user_id}",
            "expires_in": 3600
        }
        headers = {
            "Crypto-Pay-API-Token": CRYPTOBOT_TOKEN,
            "Content-Type": "application/json"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as resp:
                data = await resp.json()
                logging.info(f"CryptoBot create response: {data}")
                if data.get("ok") and data.get("result"):
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
        url = "https://pay.crypt.bot/api/getInvoices"
        params = {"invoice_ids": str(invoice_id)}
        headers = {
            "Crypto-Pay-API-Token": CRYPTOBOT_TOKEN,
            "Content-Type": "application/json"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as resp:
                text = await resp.text()
                logging.info(f"CryptoBot check response: {text}")
                
                try:
                    data = json.loads(text)
                except json.JSONDecodeError:
                    return {"success": False, "error": f"Ответ не JSON: {text[:100]}"}
                
                if data.get("ok") and data.get("result"):
                    invoices = data.get("result", [])
                    for invoice in invoices:
                        if invoice.get("status") == "paid":
                            return {
                                "success": True,
                                "paid": True,
                                "amount": float(invoice.get("amount"))
                            }
                    return {"success": True, "paid": False, "status": "pending"}
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

# ============ МЕНЮ ============
def main_menu():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Профиль", callback_data="profile")],
        [InlineKeyboardButton(text="📦 Маркет", callback_data="market")],
        [InlineKeyboardButton(text="ℹ️ Информация", callback_data="info")],
    ])
    return keyboard

def market_menu():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📱 Аккаунты", callback_data="category_accounts")],
        [InlineKeyboardButton(text="📦 Паки", callback_data="category_packs")],
        [InlineKeyboardButton(text="🔌 Proxy", callback_data="category_proxy")],
        [InlineKeyboardButton(text="⭐ Premium", callback_data="category_premium")],
        [InlineKeyboardButton(text="🌟 Telegram Stars", callback_data="category_stars")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")]
    ])
    return keyboard

def profile_menu():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Пополнить", callback_data="deposit")],
        [InlineKeyboardButton(text="📜 История", callback_data="my_accounts")],
        [InlineKeyboardButton(text="📱 Мои аккаунты", callback_data="my_accounts")],
        [InlineKeyboardButton(text="🔌 Мои прокси", callback_data="my_proxies")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")]
    ])
    return keyboard

def back_button():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")]
    ])

# ============ СТАРТ ============
@dp.message(Command("start"))
async def start(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or None
    
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
            "INSERT INTO users (id, balance, join_date, username) VALUES (?, 0, ?, ?)",
            (user_id, join_date, username)
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

👇 *Выберите действие в меню:*
        """
        
        await message.answer(
            welcome_text,
            parse_mode="Markdown",
            reply_markup=main_menu()
        )
    else:
        db.close()
        
        welcome_back_text = """
🌟 *ДОБРО ПОЖАЛОВАТЬ ОБРАТНО В OksiShop!* 🌟

👇 *Выберите действие в меню:*
        """
        
        await message.answer(
            welcome_back_text,
            parse_mode="Markdown",
            reply_markup=main_menu()
        )

# ============ НАЗАД В МЕНЮ ============
@dp.callback_query(lambda c: c.data == "back_to_menu")
async def back_to_menu(callback: CallbackQuery):
    try:
        await callback.answer()
    except:
        pass
    
    await callback.message.edit_text(
        "🌟 *ГЛАВНОЕ МЕНЮ* 🌟\n\n"
        "👇 *Выберите действие:*",
        parse_mode="Markdown",
        reply_markup=main_menu()
    )

# ============ МАРКЕТ ============
@dp.callback_query(lambda c: c.data == "market")
async def show_market(callback: CallbackQuery):
    try:
        await callback.answer()
    except:
        pass
    
    market_text = """
📦 *РАЗДЕЛЫ ТОВАРОВ МАРКЕТА* 📦

Выберите категорию:

📱 *Аккаунты* — соцсети, игры, почты
📦 *Паки* — готовые наборы аккаунтов
🔌 *Proxy* — анонимные прокси-серверы
⭐ *Premium* — премиум аккаунты
🌟 *Telegram Stars* — звёзды для Telegram
"""
    
    await callback.message.edit_text(
        market_text,
        parse_mode="Markdown",
        reply_markup=market_menu()
    )

# ============ КАТЕГОРИИ ТОВАРОВ ============
@dp.callback_query(lambda c: c.data and c.data.startswith("category_"))
async def show_category(callback: CallbackQuery):
    try:
        await callback.answer()
    except:
        pass
    
    category_map = {
        "category_accounts": ("📱 Аккаунты", "accounts"),
        "category_packs": ("📦 Паки", "packs"),
        "category_proxy": ("🔌 Proxy", "proxy"),
        "category_premium": ("⭐ Premium", "premium"),
        "category_stars": ("🌟 Telegram Stars", "stars")
    }
    
    category_name, category_key = category_map.get(callback.data, ("Категория", "default"))
    
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT id, name, price, stock, image FROM products WHERE category = ? AND stock > 0", (category_key,))
    products = cursor.fetchall()
    db.close()
    
    if not products:
        await callback.message.edit_text(
            f"{category_name}\n\n"
            "😔 *Товаров в этой категории пока нет!*\n"
            "🔄 Загляните позже — мы постоянно обновляем ассортимент.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="market")]
            ])
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
    keyboard.inline_keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="market")])
    
    await callback.message.edit_text(
        f"{category_name}\n\n"
        "👇 *Нажмите на товар для просмотра:*",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

# ============ ПРОСМОТР ТОВАРА ============
@dp.callback_query(lambda c: c.data and c.data.startswith("view_"))
async def view_product(callback: CallbackQuery):
    try:
        await callback.answer()
    except:
        pass
    
    product_id = int(callback.data.split("_")[1])
    
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT id, name, price, stock, image FROM products WHERE id = ?", (product_id,))
    product = cursor.fetchone()
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
        [InlineKeyboardButton(text="🔙 Назад", callback_data="market")]
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

# ============ ПОКУПКА ============
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
            f"💰 Пополните баланс в профиле!",
            parse_mode="Markdown",
            reply_markup=back_button()
        )
        db.close()
        return
    
    cursor.execute("SELECT id, data, proxy FROM accounts WHERE product_id = ? AND status = 'available' LIMIT 1", (product_id,))
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
    
    acc_id, acc_data, proxy = acc
    
    cursor.execute("UPDATE users SET balance = balance - ? WHERE id = ?", (price, user_id))
    cursor.execute("UPDATE accounts SET status = 'sold', buyer_id = ?, buy_date = ? WHERE id = ?", 
                   (user_id, datetime.now().strftime("%d.%m.%Y %H:%M"), acc_id))
    db.commit()
    db.close()
    
    # Формируем данные с прокси, если есть
    account_info = acc_data
    if proxy:
        account_info += f"\n🔌 Proxy: `{proxy}`"
    
    await callback.message.edit_text(
        f"✅ *ПОКУПКА УСПЕШНА!* ✅\n\n"
        f"📌 Товар: {name}\n"
        f"💰 Списано: {price} ₽\n"
        f"⏰ Время покупки: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
        f"📝 *Данные аккаунта:*\n"
        f"`{account_info}`\n\n"
        f"⚠️ *ВАЖНО:*\n"
        f"⏳ Гарантия 1 час с момента получения\n"
        f"🔒 Проверьте данные сразу!\n"
        f"📩 При проблемах пишите: @YoungTrappa8122\n\n"
        f"🌟 Спасибо за покупку!",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📦 В маркет", callback_data="market")],
            [InlineKeyboardButton(text="🏠 В меню", callback_data="back_to_menu")]
        ])
    )

# ============ ПРОФИЛЬ ============
@dp.callback_query(lambda c: c.data == "profile")
async def show_profile(callback: CallbackQuery):
    try:
        await callback.answer()
    except:
        pass
    
    user_id = callback.from_user.id
    is_admin = (user_id == ADMIN_ID)
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
    
    # Определяем статус пользователя
    if total_spent >= 5000:
        status = "👑 VIP клиент"
    elif total_spent >= 1000:
        status = "💎 Постоянный клиент"
    elif total_bought >= 5:
        status = "🌟 Активный покупатель"
    else:
        status = "🆕 Пользователь"
    
    profile_text = f"""
🔍 *ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ* 🔍
━━━━━━━━━━━━━━━━━━━

🆔 *ID:* `{user_id}`
👤 *Юзернейм:* {username}
📅 *Дата регистрации:* {join_date}

━━━━━━━━━━━━━━━━━━━
💰 *БАЛАНС:* {balance} ₽
📊 *Статус:* {status}
📦 *Покупок:* {total_bought}
💳 *Потрачено:* {total_spent} ₽
━━━━━━━━━━━━━━━━━━━

📩 По вопросам: @YoungTrappa8122
"""
    
    keyboard = profile_menu()
    
    await callback.message.edit_text(
        profile_text,
        parse_mode="Markdown",
        reply_markup=keyboard
    )

# ============ МОИ ПОКУПКИ (ИСТОРИЯ) ============
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
        SELECT p.name, a.data, a.buy_date, p.price, a.proxy
        FROM accounts a 
        JOIN products p ON a.product_id = p.id 
        WHERE a.status = 'sold' AND a.buyer_id = ?
        ORDER BY a.id DESC 
        LIMIT 10
    """, (user_id,))
    accounts = cursor.fetchall()
    db.close()
    
    if not accounts:
        await callback.message.edit_text(
            "📭 *У вас пока нет купленных аккаунтов!*\n\n"
            "🛒 Перейдите в раздел «Маркет» и сделайте свою первую покупку! 🚀",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="profile")]
            ])
        )
        return
    
    text = "📜 *ИСТОРИЯ ПОКУПОК* 📜\n"
    text += "━━━━━━━━━━━━━━━━━━━\n"
    text += f"📊 Всего: {len(accounts)} (последние 10)\n\n"
    
    for idx, acc in enumerate(accounts, 1):
        name, data, buy_date, price, proxy = acc
        text += f"🔹 *{idx}. {name}*\n"
        text += f"📝 Данные: `{data}`\n"
        if proxy:
            text += f"🔌 Proxy: `{proxy}`\n"
        text += f"💰 Цена: {price} ₽\n"
        text += f"⏰ Куплен: {buy_date}\n\n"
    
    text += "━━━━━━━━━━━━━━━━━━━\n"
    text += "⚠️ *Напоминание:*\n"
    text += "⏳ Гарантия 1 час с момента покупки\n"
    text += "📩 При проблемах: @YoungTrappa8122"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="profile")]
    ])
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=keyboard
    )

# ============ МОИ ПРОКСИ ============
@dp.callback_query(lambda c: c.data == "my_proxies")
async def show_my_proxies(callback: CallbackQuery):
    try:
        await callback.answer()
    except:
        pass
    
    user_id = callback.from_user.id
    
    db = get_db()
    cursor = db.cursor()
    cursor.execute("""
        SELECT data, proxy, buy_date
        FROM accounts 
        WHERE status = 'sold' AND buyer_id = ? AND proxy IS NOT NULL AND proxy != ''
        ORDER BY id DESC 
        LIMIT 10
    """, (user_id,))
    proxies = cursor.fetchall()
    db.close()
    
    if not proxies:
        await callback.message.edit_text(
            "🔌 *Мои прокси*\n\n"
            "📭 У вас пока нет купленных прокси!",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="profile")]
            ])
        )
        return
    
    text = "🔌 *МОИ ПРОКСИ* 🔌\n"
    text += "━━━━━━━━━━━━━━━━━━━\n\n"
    
    for idx, (data, proxy, buy_date) in enumerate(proxies, 1):
        text += f"🔹 *{idx}.*\n"
        text += f"📝 Данные: `{data}`\n"
        text += f"🔌 Proxy: `{proxy}`\n"
        text += f"⏰ Куплен: {buy_date}\n\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="profile")]
    ])
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=keyboard
    )

# ============ ИНФОРМАЦИЯ ============
@dp.callback_query(lambda c: c.data == "info")
async def show_info(callback: CallbackQuery):
    try:
        await callback.answer()
    except:
        pass
    
    info_text = """
ℹ️ *О МАГАЗИНЕ* ℹ️
━━━━━━━━━━━━━━━━━━━

📌 *OksiShop* — это удобный инструмент для тех, кто ценит скорость, анонимность и стабильность.

✅ *Что мы предлагаем:*
• Качественные аккаунты
• Быстрая автоматическая выдача
• Гарантия 1 час
• Поддержка 24/7

💰 *Оплата:*
• CryptoBot (USDT, TON, BTC, ETH)
• xRocket (TON)

📩 *Поддержка:* @YoungTrappa8122

🌟 *Приятных покупок!*
"""
    
    await callback.message.edit_text(
        info_text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")]
        ])
    )

# ============ ПОПОЛНЕНИЕ БАЛАНСА ============
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
"""
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 CryptoBot", callback_data="deposit_cryptobot")],
        [InlineKeyboardButton(text="🚀 xRocket", callback_data="deposit_xrocket")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="profile")]
    ])
    
    await callback.message.edit_text(
        caption,
        parse_mode="Markdown",
        reply_markup=keyboard
    )

# ============ CRYPTOBOT ПОПОЛНЕНИЕ ============
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
        f"📌 После оплаты баланс начислится автоматически!\n"
        f"⏳ Если через 2 минуты баланс не пришёл — нажмите «Проверить оплату».",
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
            f"Подождите 1-2 минуты и попробуйте снова.\n"
            f"Если оплата прошла, но баланс не начислен — напишите @YoungTrappa8122",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Проверить снова", callback_data=f"check_cb_{invoice_id}")],
                [InlineKeyboardButton(text="🏠 В меню", callback_data="back_to_menu")]
            ])
        )

# ============ XROCKET ПОПОЛНЕНИЕ ============
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
    
    invoice_id = callback.data.split("_")[2]
    user_id = callback.from_user.id
    
    # Сначала проверяем в БД, не оплачен ли уже
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT status FROM pending_payments WHERE invoice_id = ? AND system = 'xrocket'", (invoice_id,))
    result = cursor.fetchone()
    
    if result and result[0] == "paid":
        db.close()
        await callback.message.edit_text(
            f"✅ *Оплата уже была подтверждена!* ✅\n\n"
            f"💰 Баланс начислен.",
            parse_mode="Markdown",
            reply_markup=main_menu()
        )
        return
    db.close()
    
    await callback.message.edit_text(
        "⏳ *Проверка оплаты...*\n\n"
        "Для xRocket пока доступна ручная проверка.\n"
        "Пожалуйста, свяжитесь с админом для ручного пополнения: @YoungTrappa8122",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏠 В меню", callback_data="back_to_menu")]
        ])
    )

# ============ РЕФЕРАЛКА ============
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
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")]
    ])
    
    await callback.message.edit_text(
        caption,
        parse_mode="Markdown",
        reply_markup=keyboard
    )

# ============ КОПИРОВАТЬ РЕФЕРАЛКУ ============
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

# ============ ТЕХПОДДЕРЖКА ============
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
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")]
    ])
    
    await callback.message.edit_text(
        caption,
        parse_mode="Markdown",
        reply_markup=keyboard
    )

# ============ ПОМОЩЬ ============
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
    
    await callback.message.edit_text(
        help_text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")]
        ])
    )

# ============ АДМИН: ПОПОЛНЕНИЕ БАЛАНСА ============
@dp.message(Command("add"))
async def add_balance(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Доступ запрещен")
        return
    
    try:
        parts = message.text.split()
        if len(parts) < 3:
            await message.answer(
                "❌ *Неверный формат!*\n\n"
                "Используйте:\n"
                "`/add [user_id] [сумма]` — по ID\n"
                "`/add @username [сумма]` — по юзернейму\n\n"
                "Пример: `/add 123456789 100`",
                parse_mode="Markdown"
            )
            return
        
        target = parts[1]
        amount = int(parts[2])
        
        if amount <= 0:
            await message.answer("❌ Сумма должна быть больше 0!")
            return
        
        db = get_db()
        cursor = db.cursor()
        
        if target.startswith('@'):
            username = target[1:]
            cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
            result = cursor.fetchone()
            if not result:
                await message.answer(f"❌ Пользователь {target} не найден в базе!")
                db.close()
                return
            user_id = result[0]
        else:
            user_id = int(target)
            cursor.execute("SELECT id FROM users WHERE id = ?", (user_id,))
            if not cursor.fetchone():
                await message.answer(f"❌ Пользователь с ID {user_id} не найден!")
                db.close()
                return
        
        cursor.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (amount, user_id))
        db.commit()
        db.close()
        
        await message.answer(f"✅ Баланс пользователя {target} пополнен на {amount} ₽")
        
        try:
            await bot.send_message(
                user_id,
                f"💰 *Баланс пополнен!* 💰\n\n"
                f"✅ Сумма: +{amount} ₽\n"
                f"📊 Проверьте баланс в профиле!\n"
                f"🛒 Приятных покупок! 🌟",
                parse_mode="Markdown"
            )
        except:
            pass
            
    except ValueError:
        await message.answer("❌ Сумма должна быть числом!")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")

# ============ ПОЛУЧИТЬ FILE_ID ============
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
