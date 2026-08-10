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
        return "✅ CryptoBot webhook active", 200
    try:
        data = request.get_json()
        logging.info(f"📩 Webhook: {data}")
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
                logging.info(f"✅ +{amount_rub} ₽ user {user_id}")
                try:
                    asyncio.run_coroutine_threadsafe(
                        bot.send_message(user_id, f"✨ *Оплата прошла!* +{amount_rub} ₽", parse_mode="Markdown"),
                        asyncio.get_event_loop()
                    )
                except:
                    pass
                return "OK", 200
        return "OK", 200
    except Exception as e:
        logging.error(f"Webhook error: {e}")
        return "Error", 500

@app.route('/xrocket_webhook', methods=['GET', 'POST'])
def xrocket_webhook():
    if request.method == 'GET':
        return "✅ xRocket webhook active", 200
    return "OK", 200

# ============ БОТ ============
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

def get_db():
    db_path = os.path.join(os.path.dirname(__file__), "shop.db")
    db = sqlite3.connect(db_path)
    cursor = db.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY, balance INTEGER DEFAULT 0, join_date TEXT, username TEXT)''')
    cursor.execute("PRAGMA table_info(users)")
    columns = [col[1] for col in cursor.fetchall()]
    if "username" not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN username TEXT")
    cursor.execute('''CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, price INTEGER, stock INTEGER, 
        image TEXT, category TEXT DEFAULT 'accounts')''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT, product_id INTEGER, data TEXT, proxy TEXT,
        status TEXT DEFAULT 'available', buyer_id INTEGER, buy_date TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS pending_payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, invoice_id TEXT,
        amount REAL, system TEXT, created_at TEXT, status TEXT DEFAULT 'pending')''')
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
            await bot.send_message(referrer_id, f"🎉 *Реферал!* +{BONUS_AMOUNT} ₽", parse_mode="Markdown")
        except:
            pass
        return True, BONUS_AMOUNT
    db.close()
    return False, 0

# ============ CRYPTOBOT ============
async def create_cryptobot_invoice(user_id, amount_usd):
    try:
        url = "https://pay.crypt.bot/api/createInvoice"
        payload = {"currency_type": "fiat", "fiat": "USD", "amount": str(amount_usd),
                   "description": "OksiShop", "payload": f"user_{user_id}", "expires_in": 3600}
        headers = {"Crypto-Pay-API-Token": CRYPTOBOT_TOKEN, "Content-Type": "application/json"}
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as resp:
                data = await resp.json()
                logging.info(f"CryptoBot: {data}")
                if data.get("ok") and data.get("result"):
                    invoice = data.get("result")
                    return {"success": True, "invoice_id": invoice.get("invoice_id"),
                            "pay_url": invoice.get("bot_invoice_url"), "amount": amount_usd}
                return {"success": False, "error": data.get("error", "Unknown")}
    except Exception as e:
        logging.error(f"CryptoBot error: {e}")
        return {"success": False, "error": str(e)}

async def check_cryptobot_payment(invoice_id):
    try:
        url = "https://pay.crypt.bot/api/getInvoices"
        params = {"invoice_ids": str(invoice_id)}
        headers = {"Crypto-Pay-API-Token": CRYPTOBOT_TOKEN, "Content-Type": "application/json"}
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as resp:
                text = await resp.text()
                try:
                    data = json.loads(text)
                except:
                    return {"success": False, "error": f"Не JSON: {text[:50]}"}
                if data.get("ok") and data.get("result"):
                    for invoice in data.get("result", []):
                        if invoice.get("status") == "paid":
                            return {"success": True, "paid": True, "amount": float(invoice.get("amount"))}
                    return {"success": True, "paid": False, "status": "pending"}
                return {"success": False, "error": data.get("error", "Unknown")}
    except Exception as e:
        return {"success": False, "error": str(e)}

# ============ XROCKET ============
async def create_xrocket_invoice(user_id, amount_usd):
    try:
        amount_ton = amount_usd / 5.0
        url = "https://pay.xrocket.tg/invoice"
        headers = {"Rocket-Pay-Key": XROCKET_API_KEY, "Content-Type": "application/json"}
        payload = {"currency": "TON", "amount": str(round(amount_ton, 2)),
                   "description": "OksiShop", "expiresIn": 3600}
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as resp:
                data = await resp.json()
                if data.get("status") == "success":
                    invoice = data.get("data", {})
                    return {"success": True, "invoice_id": invoice.get("invoiceId"),
                            "pay_url": invoice.get("link"), "amount": amount_usd}
                return {"success": False, "error": data.get("error", "Unknown")}
    except Exception as e:
        return {"success": False, "error": str(e)}

# ============ МЕНЮ (ИСПРАВЛЕНЫ) ============
def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Профиль", callback_data="profile"),
         InlineKeyboardButton(text="🛍️ Маркет", callback_data="market")],
        [InlineKeyboardButton(text="🎁 Рефералка", callback_data="referral"),
         InlineKeyboardButton(text="🛠 Поддержка", callback_data="support")],
        [InlineKeyboardButton(text="ℹ️ О нас", callback_data="info")]
    ])

def market_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📱 Аккаунты", callback_data="category_accounts"),
         InlineKeyboardButton(text="📦 Паки", callback_data="category_packs")],
        [InlineKeyboardButton(text="🔌 Proxy", callback_data="category_proxy"),
         InlineKeyboardButton(text="⭐ Premium", callback_data="category_premium")],
        [InlineKeyboardButton(text="🌟 Telegram Stars", callback_data="category_stars")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_menu")]
    ])

def profile_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Пополнить", callback_data="deposit"),
         InlineKeyboardButton(text="📜 История", callback_data="my_accounts")],
        [InlineKeyboardButton(text="📱 Мои акки", callback_data="my_accounts"),
         InlineKeyboardButton(text="🔌 Мои прокси", callback_data="my_proxies")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_menu")]
    ])

def deposit_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 10 ₽", callback_data="cb_amount_10"),
         InlineKeyboardButton(text="💰 50 ₽", callback_data="cb_amount_50")],
        [InlineKeyboardButton(text="💰 100 ₽", callback_data="cb_amount_100"),
         InlineKeyboardButton(text="💰 500 ₽", callback_data="cb_amount_500")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="deposit")]
    ])

def back_button():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_menu")]
    ])

# ============ СТАРТ ============
@dp.message(Command("start"))
async def start(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or None
    args = message.text.split()
    ref_code = args[1] if len(args) > 1 else None
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT id FROM users WHERE id = ?", (user_id,))
    if not cursor.fetchone():
        join_date = datetime.now().strftime("%d.%m.%Y %H:%M")
        cursor.execute("INSERT INTO users (id, balance, join_date, username) VALUES (?, 0, ?, ?)",
                       (user_id, join_date, username))
        db.commit()
        if ref_code:
            await apply_referral(user_id, ref_code)
        db.close()
        text = "✨ *OksiShop*\n🔥 Добро пожаловать!\n💳 CryptoBot, xRocket\n👇 Выбери действие:"
    else:
        db.close()
        text = "✨ *OksiShop*\n👋 С возвращением!\n👇 Выбери действие:"
    await message.answer(text, parse_mode="Markdown", reply_markup=main_menu())

# ============ НАЗАД ============
@dp.callback_query(lambda c: c.data == "back_to_menu")
async def back_to_menu(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_text("✨ *OksiShop*\n👇 Выбери действие:", parse_mode="Markdown", reply_markup=main_menu())

# ============ МАРКЕТ ============
@dp.callback_query(lambda c: c.data == "market")
async def show_market(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_text("🛍️ *Маркет*\n📂 Категории:\n👇 Выбери:", parse_mode="Markdown", reply_markup=market_menu())

# ============ КАТЕГОРИИ ============
@dp.callback_query(lambda c: c.data and c.data.startswith("category_"))
async def show_category(callback: CallbackQuery):
    await callback.answer()
    cat_map = {
        "category_accounts": ("📱 Аккаунты", "accounts"),
        "category_packs": ("📦 Паки", "packs"),
        "category_proxy": ("🔌 Proxy", "proxy"),
        "category_premium": ("⭐ Premium", "premium"),
        "category_stars": ("🌟 Telegram Stars", "stars")
    }
    cat_name, cat_key = cat_map.get(callback.data, ("Категория", "default"))
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT id, name, price, stock, image FROM products WHERE category = ? AND stock > 0", (cat_key,))
    products = cursor.fetchall()
    db.close()
    if not products:
        await callback.message.edit_text(f"{cat_name}\n😔 Товаров пока нет", parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(text="◀️ Назад", callback_data="market")]]))
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for p in products:
        kb.inline_keyboard.append([
            InlineKeyboardButton(text=f"📌 {p[1]} — {p[2]} ₽ (осталось: {p[3]})", callback_data=f"view_{p[0]}")
        ])
    kb.inline_keyboard.append([InlineKeyboardButton(text="◀️ Назад", callback_data="market")])
    await callback.message.edit_text(f"{cat_name}\n👇 Нажми на товар:", parse_mode="Markdown", reply_markup=kb)

# ============ ПРОСМОТР ТОВАРА ============
@dp.callback_query(lambda c: c.data and c.data.startswith("view_"))
async def view_product(callback: CallbackQuery):
    await callback.answer()
    product_id = int(callback.data.split("_")[1])
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT id, name, price, stock, image FROM products WHERE id = ?", (product_id,))
    p = cursor.fetchone()
    db.close()
    if not p:
        await callback.message.edit_text("❌ Товар не найден", reply_markup=back_button())
        return
    pid, name, price, stock, image = p
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 Купить", callback_data=f"buy_{pid}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="market")]
    ])
    caption = f"*{name}*\n💰 {price} ₽ | 📊 {stock} шт.\n✅ Гарантия 1 час"
    if image:
        await callback.message.delete()
        await callback.message.answer_photo(photo=image, caption=caption, parse_mode="Markdown", reply_markup=kb)
    else:
        await callback.message.edit_text(caption, parse_mode="Markdown", reply_markup=kb)

# ============ ПОКУПКА ============
@dp.callback_query(lambda c: c.data and c.data.startswith("buy_"))
async def buy_product(callback: CallbackQuery):
    await callback.answer()
    product_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT balance FROM users WHERE id = ?", (user_id,))
    balance = cursor.fetchone()[0]
    cursor.execute("SELECT price, name, stock FROM products WHERE id = ?", (product_id,))
    price, name, stock = cursor.fetchone()
    if balance < price:
        await callback.message.edit_text(f"❌ Не хватает!\n💰 {price} ₽ | У тебя: {balance} ₽",
            reply_markup=back_button())
        db.close()
        return
    cursor.execute("SELECT id, data, proxy FROM accounts WHERE product_id = ? AND status = 'available' LIMIT 1", (product_id,))
    acc = cursor.fetchone()
    if not acc:
        await callback.message.edit_text("😔 Аккаунты закончились!", reply_markup=back_button())
        db.close()
        return
    acc_id, acc_data, proxy = acc
    cursor.execute("UPDATE users SET balance = balance - ? WHERE id = ?", (price, user_id))
    cursor.execute("UPDATE accounts SET status = 'sold', buyer_id = ?, buy_date = ? WHERE id = ?",
                   (user_id, datetime.now().strftime("%d.%m.%Y %H:%M"), acc_id))
    db.commit()
    db.close()
    data_text = acc_data
    if proxy:
        data_text += f"\n🔌 Proxy: `{proxy}`"
    await callback.message.edit_text(f"✅ *Куплено!*\n📌 {name}\n💰 -{price} ₽\n📝 `{data_text}`\n⚠️ Гарантия 1 час",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(text="🛍️ В маркет", callback_data="market")],
            [InlineKeyboardButton(text="🏠 В меню", callback_data="back_to_menu")]
        ]))

# ============ ПРОФИЛЬ ============
@dp.callback_query(lambda c: c.data == "profile")
async def show_profile(callback: CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    username = f"@{callback.from_user.username}" if callback.from_user.username else "❌"
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT balance, join_date FROM users WHERE id = ?", (user_id,))
    balance, join_date = cursor.fetchone() or (0, "❌")
    cursor.execute("SELECT COUNT(*) FROM accounts WHERE status = 'sold' AND buyer_id = ?", (user_id,))
    total_bought = cursor.fetchone()[0]
    cursor.execute("SELECT SUM(p.price) FROM accounts a JOIN products p ON a.product_id = p.id WHERE a.status = 'sold' AND a.buyer_id = ?", (user_id,))
    total_spent = cursor.fetchone()[0] or 0
    db.close()
    if total_spent >= 5000:
        status = "👑 VIP"
    elif total_spent >= 1000:
        status = "💎 Постоянный"
    elif total_bought >= 5:
        status = "🌟 Активный"
    else:
        status = "🆕 Новичок"
    text = f"👤 *Профиль*\n🆔 `{user_id}`\n👤 {username}\n📅 {join_date}\n💰 Баланс: {balance} ₽\n📊 Статус: {status}\n📦 Покупок: {total_bought}\n💳 Потрачено: {total_spent} ₽"
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=profile_menu())

# ============ ИСТОРИЯ ============
@dp.callback_query(lambda c: c.data == "my_accounts")
async def show_my_accounts(callback: CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    db = get_db()
    cursor = db.cursor()
    cursor.execute("""SELECT p.name, a.data, a.buy_date, p.price, a.proxy FROM accounts a 
        JOIN products p ON a.product_id = p.id WHERE a.status = 'sold' AND a.buyer_id = ? 
        ORDER BY a.id DESC LIMIT 10""", (user_id,))
    accs = cursor.fetchall()
    db.close()
    if not accs:
        await callback.message.edit_text("📭 История пуста", reply_markup=profile_menu())
        return
    text = "📜 *История*\n"
    for i, (name, data, date, price, proxy) in enumerate(accs, 1):
        text += f"{i}. {name} — {price} ₽\n📝 `{data}`"
        if proxy:
            text += f"\n🔌 `{proxy}`"
        text += f"\n⏰ {date}\n\n"
    await callback.message.edit_text(text[:4000], parse_mode="Markdown", reply_markup=profile_menu())

# ============ МОИ ПРОКСИ ============
@dp.callback_query(lambda c: c.data == "my_proxies")
async def show_my_proxies(callback: CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    db = get_db()
    cursor = db.cursor()
    cursor.execute("""SELECT data, proxy, buy_date FROM accounts 
        WHERE status = 'sold' AND buyer_id = ? AND proxy IS NOT NULL AND proxy != '' 
        ORDER BY id DESC LIMIT 10""", (user_id,))
    proxies = cursor.fetchall()
    db.close()
    if not proxies:
        await callback.message.edit_text("🔌 Прокси не найдены", reply_markup=profile_menu())
        return
    text = "🔌 *Мои прокси*\n"
    for i, (data, proxy, date) in enumerate(proxies, 1):
        text += f"{i}. 📝 `{data}`\n🔌 `{proxy}`\n⏰ {date}\n\n"
    await callback.message.edit_text(text[:4000], parse_mode="Markdown", reply_markup=profile_menu())

# ============ ИНФО ============
@dp.callback_query(lambda c: c.data == "info")
async def show_info(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_text(
        "ℹ️ *OksiShop*\n✅ Аккаунты, прокси, Premium, Stars\n💰 CryptoBot, xRocket\n📩 @YoungTrappa8122",
        parse_mode="Markdown", reply_markup=back_button()
    )

# ============ ПОПОЛНЕНИЕ ============
@dp.callback_query(lambda c: c.data == "deposit")
async def show_deposit(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_text(
        "💰 *Пополнение*\n💳 CryptoBot\n🚀 xRocket\n👇 Выбери способ:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(text="💳 CryptoBot", callback_data="deposit_cryptobot"),
             InlineKeyboardButton(text="🚀 xRocket", callback_data="deposit_xrocket")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="profile")]
        ])
    )

# ============ CRYPTOBOT ПОПОЛНЕНИЕ ============
@dp.callback_query(lambda c: c.data == "deposit_cryptobot")
async def deposit_cryptobot(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_text("💳 *CryptoBot*\n👇 Выбери сумму:", parse_mode="Markdown", reply_markup=deposit_menu())

@dp.callback_query(lambda c: c.data and c.data.startswith("cb_amount_"))
async def process_cryptobot_amount(callback: CallbackQuery):
    await callback.answer()
    amount_rub = float(callback.data.split("_")[2])
    amount_usd = amount_rub / 100
    user_id = callback.from_user.id
    result = await create_cryptobot_invoice(user_id, amount_usd)
    if not result["success"]:
        await callback.message.edit_text(f"❌ Ошибка: {result['error']}", reply_markup=back_button())
        return
    await callback.message.edit_text(
        f"✅ *Счёт создан!*\n💰 {amount_rub} ₽\n🔗 [Оплатить]({result['pay_url']})\n📌 После оплаты нажми «Проверить»",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(text="✅ Проверить", callback_data=f"check_cb_{result['invoice_id']}")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="deposit")]
        ])
    )

# ============ ПРОВЕРКА CRYPTOBOT ============
@dp.callback_query(lambda c: c.data and c.data.startswith("check_cb_"))
async def check_cryptobot_payment_handler(callback: CallbackQuery):
    await callback.answer()
    invoice_id = callback.data.split("_")[2]
    user_id = callback.from_user.id
    result = await check_cryptobot_payment(invoice_id)
    if not result["success"]:
        await callback.message.edit_text(f"❌ Ошибка: {result['error']}", reply_markup=back_button())
        return
    if result.get("paid"):
        db = get_db()
        cursor = db.cursor()
        amount_rub = int(result["amount"] * 100)
        cursor.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (amount_rub, user_id))
        db.commit()
        db.close()
        await callback.message.edit_text(f"✅ *Оплата прошла!* +{amount_rub} ₽", parse_mode="Markdown", reply_markup=main_menu())
    else:
        await callback.message.edit_text("⏳ Ещё не оплачено", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(text="🔄 Проверить", callback_data=f"check_cb_{invoice_id}")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="deposit")]
        ]))

# ============ XROCKET ============
@dp.callback_query(lambda c: c.data == "deposit_xrocket")
async def deposit_xrocket(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_text("🚀 *xRocket*\n👇 Выбери сумму:", parse_mode="Markdown", reply_markup=deposit_menu())

@dp.callback_query(lambda c: c.data and c.data.startswith("xr_amount_"))
async def process_xrocket_amount(callback: CallbackQuery):
    await callback.answer()
    amount_rub = float(callback.data.split("_")[2])
    amount_usd = amount_rub / 100
    user_id = callback.from_user.id
    result = await create_xrocket_invoice(user_id, amount_usd)
    if not result["success"]:
        await callback.message.edit_text(f"❌ Ошибка: {result['error']}", reply_markup=back_button())
        return
    await callback.message.edit_text(
        f"✅ *Счёт создан!*\n💰 {amount_rub} ₽\n🔗 [Оплатить]({result['pay_url']})\n📌 После оплаты нажми «Проверить»",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(text="✅ Проверить", callback_data=f"check_xr_{result['invoice_id']}")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="deposit")]
        ])
    )

# ============ ПРОВЕРКА XROCKET ============
@dp.callback_query(lambda c: c.data and c.data.startswith("check_xr_"))
async def check_xrocket_payment_handler(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_text(
        "⏳ Проверка...\n📩 Напиши @YoungTrappa8122",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(text="📩 Написать", url="https://t.me/YoungTrappa8122")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="deposit")]
        ])
    )

# ============ РЕФЕРАЛКА ============
@dp.callback_query(lambda c: c.data == "referral")
async def show_referral(callback: CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    ref_code = get_or_create_ref_code(user_id)
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT COUNT(*) FROM users WHERE referrer_id = ?", (user_id,))
    count = cursor.fetchone()[0]
    cursor.execute("SELECT ref_bonus FROM users WHERE id = ?", (user_id,))
    bonus = cursor.fetchone()[0] or 0
    db.close()
    link = f"https://t.me/Oksitocin_Shop_Bot?start={ref_code}"
    text = f"🎁 *Рефералка*\n👥 Приглашено: {count}\n💰 Заработано: {bonus} ₽\n🔑 Код: `{ref_code}`\n🔗 {link}"
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton(text="📋 Копировать", callback_data=f"copy_ref_{ref_code}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_menu")]
    ]))

# ============ КОПИРОВАТЬ РЕФЕРАЛКУ ============
@dp.callback_query(lambda c: c.data and c.data.startswith("copy_ref_"))
async def copy_referral(callback: CallbackQuery):
    await callback.answer()
    ref_code = callback.data.split("_")[2]
    link = f"https://t.me/Oksitocin_Shop_Bot?start={ref_code}"
    await callback.message.answer(f"🔗 `{link}`", parse_mode="Markdown")
    await callback.answer("📋 Скопировано!")

# ============ ПОДДЕРЖКА ============
@dp.callback_query(lambda c: c.data == "support")
async def show_support(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_text(
        "🛠 *Поддержка*\n📩 @YoungTrappa8122\n⏰ 24/7",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(text="📩 Написать", url="https://t.me/YoungTrappa8122")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_menu")]
        ])
    )

# ============ АДМИН ============
@dp.message(Command("add"))
async def add_balance(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        parts = message.text.split()
        if len(parts) < 3:
            await message.answer("❌ Формат: /add @username 100 или /add 123456789 100")
            return
        target = parts[1]
        amount = int(parts[2])
        if amount <= 0:
            await message.answer("❌ Сумма > 0")
            return
        db = get_db()
        cursor = db.cursor()
        if target.startswith('@'):
            username = target[1:]
            cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
            res = cursor.fetchone()
            if not res:
                await message.answer(f"❌ {target} не найден")
                db.close()
                return
            user_id = res[0]
        else:
            user_id = int(target)
            cursor.execute("SELECT id FROM users WHERE id = ?", (user_id,))
            if not cursor.fetchone():
                await message.answer(f"❌ {user_id} не найден")
                db.close()
                return
        cursor.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (amount, user_id))
        db.commit()
        db.close()
        await message.answer(f"✅ {target} +{amount} ₽")
        try:
            await bot.send_message(user_id, f"💰 +{amount} ₽", parse_mode="Markdown")
        except:
            pass
    except:
        await message.answer("❌ Ошибка")

# ============ GET FILE ID ============
@dp.message(Command("getid"))
async def get_file_id(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    if message.photo:
        await message.answer(f"📸 `{message.photo[-1].file_id}`", parse_mode="Markdown")
    elif message.document:
        await message.answer(f"📄 `{message.document.file_id}`", parse_mode="Markdown")

# ============ ЗАПУСК ============
async def main():
    print("🤖 Бот запущен!")
    print(f"👤 Админ ID: {ADMIN_ID}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False), daemon=True).start()
    print(f"✅ Flask на порту {port}")
    asyncio.run(main())
