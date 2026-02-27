import os
import asyncio
import logging
import re
from datetime import datetime
import pytz
import asyncpg

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove

# --- SOZLAMALAR ---
BOT_TOKEN = os.getenv("BOT_TOKEN", "8759158410:AAFH4Lz-1VsndTC4VRABU7uHYU-qCFoY60Q")
DATABASE_URL = os.getenv("DATABASE_URL")

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

db = None
state = {}  # Faqat qisqa muddatli holatlar uchun
tz = pytz.timezone("Asia/Tashkent")

# --- YORDAMCHI FUNKSIYALAR ---
def format_num(num):
    try:
        return "{:,.0f}".format(num).replace(",", " ")
    except:
        return "0"

def parse_num(text):
    clean_text = re.sub(r'[^\d]', '', text)
    return float(clean_text) if clean_text else 0

# --- BAZA BILAN ISHLASH ---
async def init_db():
    global db
    db = await asyncpg.connect(DATABASE_URL)
    
    # Foydalanuvchilar va ularning hozirgi tanlagan mijozi
    await db.execute("""
    CREATE TABLE IF NOT EXISTS users(
        user_id BIGINT PRIMARY KEY,
        selected_client_id INTEGER
    )
    """)
    
    await db.execute("""
    CREATE TABLE IF NOT EXISTS clients(
        id SERIAL PRIMARY KEY,
        name TEXT UNIQUE
    )
    """)
    
    await db.execute("""
    CREATE TABLE IF NOT EXISTS debts(
        id SERIAL PRIMARY KEY,
        client_id INTEGER REFERENCES clients(id) ON DELETE CASCADE,
        amount FLOAT,
        type TEXT,
        created TIMESTAMP
    )
    """)

# --- KLAVIATURALAR ---
def main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Mijoz qo'shish"), KeyboardButton(text="👥 Mijozlar")],
            [KeyboardButton(text="📊 Umumiy Statistika")]
        ],
        resize_keyboard=True
    )

def client_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Qarz qo'shish"), KeyboardButton(text="➖ Qarz ayirish")],
            [KeyboardButton(text="💰 Balansni ko'rish"), KeyboardButton(text="📜 Tarix")],
            [KeyboardButton(text="⬅️ Orqaga")]
        ],
        resize_keyboard=True
    )

# --- HANDLERLAR ---

@dp.message(Command("start"))
async def start(message: types.Message):
    await db.execute("INSERT INTO users(user_id) VALUES($1) ON CONFLICT DO NOTHING", message.from_user.id)
    await message.answer("🏦 Qarz CRM tizimiga xush kelibsiz!", reply_markup=main_menu())

@dp.message(F.text == "➕ Mijoz qo'shish")
async def add_client(message: types.Message):
    state[message.from_user.id] = "add_client"
    await message.answer("👤 Yangi mijoz ismini yozing:", reply_markup=ReplyKeyboardRemove())

@dp.message(lambda m: state.get(m.from_user.id) == "add_client")
async def save_client(message: types.Message):
    try:
        if message.text == "⬅️ Orqaga":
            state.pop(message.from_user.id, None)
            return await message.answer("Bekor qilindi", reply_markup=main_menu())
            
        await db.execute("INSERT INTO clients(name) VALUES($1)", message.text)
        await message.answer(f"✅ {message.text} qo'shildi.", reply_markup=main_menu())
    except asyncpg.UniqueViolationError:
        await message.answer("❌ Bu mijoz bazada bor.")
    state.pop(message.from_user.id, None)

@dp.message(F.text == "👥 Mijozlar")
async def list_clients(message: types.Message):
    rows = await db.fetch("SELECT * FROM clients ORDER BY name")
    if not rows:
        return await message.answer("Mijozlar yo'q.")
    kb = [[KeyboardButton(text=r["name"])] for r in rows]
    kb.append([KeyboardButton(text="⬅️ Orqaga")])
    await message.answer("Mijozni tanlang:", reply_markup=ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True))

@dp.message(F.text == "⬅️ Orqaga")
async def go_back(message: types.Message):
    await db.execute("UPDATE users SET selected_client_id = NULL WHERE user_id = $1", message.from_user.id)
    await message.answer("Asosiy menu", reply_markup=main_menu())

# MIJOZNI TANLASH LOGIKASI
@dp.message(lambda m: m.text not in ["➕ Mijoz qo'shish", "👥 Mijozlar", "📊 Umumiy Statistika", "➕ Qarz qo'shish", "➖ Qarz ayirish", "💰 Balansni ko'rish", "📜 Tarix", "⬅️ Orqaga"])
async def select_client(message: types.Message):
    row = await db.fetchrow("SELECT id, name FROM clients WHERE name=$1", message.text)
    if row:
        await db.execute("UPDATE users SET selected_client_id = $1 WHERE user_id = $2", row['id'], message.from_user.id)
        await message.answer(f"👤 Mijoz: **{row['name']}** tanlandi.", reply_markup=client_menu(), parse_mode="Markdown")

# QARZ VA TO'LOV AMALLARI
@dp.message(F.text.in_(["➕ Qarz qo'shish", "➖ Qarz ayirish"]))
async def ask_amount(message: types.Message):
    # Tekshirish: Mijoz tanlanganmi?
    selected = await db.fetchval("SELECT selected_client_id FROM users WHERE user_id = $1", message.from_user.id)
    if not selected:
        return await message.answer("Avval mijozni tanlang!", reply_markup=main_menu())
        
    state[message.from_user.id] = "add_debt" if message.text == "➕ Qarz qo'shish" else "minus_debt"
    await message.answer("💰 Summani kiriting:", reply_markup=ReplyKeyboardRemove())

@dp.message(lambda m: state.get(m.from_user.id) in ["add_debt", "minus_debt"])
async def save_transaction(message: types.Message):
    user_id = message.from_user.id
    mode = state[user_id]
    amount = parse_num(message.text)
    
    if amount <= 0:
        return await message.answer("❌ Faqat raqam kiriting!")

    client_id = await db.fetchval("SELECT selected_client_id FROM users WHERE user_id = $1", user_id)
    type_label = "add" if mode == "add_debt" else "minus"
    now = datetime.now(tz)

    await db.execute("INSERT INTO debts(client_id, amount, type, created) VALUES($1, $2, $3, $4)", client_id, amount, type_label, now)

    # Ma'lumotlarni olish
    client_name = await db.fetchval("SELECT name FROM clients WHERE id=$1", client_id)
    total_add = await db.fetchval("SELECT COALESCE(SUM(amount),0) FROM debts WHERE client_id=$1 AND type='add'", client_id)
    total_minus = await db.fetchval("SELECT COALESCE(SUM(amount),0) FROM debts WHERE client_id=$1 AND type='minus'", client_id)
    
    state.pop(user_id, None)
    receipt = (
        f"🧾 **AMALIYOT BAJARILDI**\n━━━━━━━━━━━━━━━\n"
        f"👤 Mijoz: **{client_name}**\n"
        f"🕒 Sana: `{now.strftime('%d.%m.%Y | %H:%M')}`\n━━━━━━━━━━━━━━━\n"
        f"{'➕' if type_label == 'add' else '➖'} Miqdor: `{format_num(amount)}` so'm\n"
        f"📉 Qoldiq: **{format_num(total_add - total_minus)}** so'm"
    )
    await message.answer(receipt, reply_markup=client_menu(), parse_mode="Markdown")

@dp.message(F.text == "💰 Balansni ko'rish")
async def show_balance(message: types.Message):
    client_id = await db.fetchval("SELECT selected_client_id FROM users WHERE user_id = $1", message.from_user.id)
    if not client_id: return await message.answer("Mijoz tanlanmagan!")
    
    add = await db.fetchval("SELECT COALESCE(SUM(amount),0) FROM debts WHERE client_id=$1 AND type='add'", client_id)
    minus = await db.fetchval("SELECT COALESCE(SUM(amount),0) FROM debts WHERE client_id=$1 AND type='minus'", client_id)
    await message.answer(f"💰 Joriy qarz: **{format_num(add-minus)}** so'm", parse_mode="Markdown")

@dp.message(F.text == "📜 Tarix")
async def show_history(message: types.Message):
    client_id = await db.fetchval("SELECT selected_client_id FROM users WHERE user_id = $1", message.from_user.id)
    rows = await db.fetch("SELECT * FROM debts WHERE client_id=$1 ORDER BY created DESC LIMIT 10", client_id)
    
    if not rows: return await message.answer("Tarix bo'sh.")
    
    res = "📜 **OXIRGI 10 TA AMALIYOT:**\n\n"
    for r in rows:
        s = "➕" if r['type'] == 'add' else "➖"
        res += f"`{r['created'].strftime('%d.%m %H:%M')}` | {s} `{format_num(r['amount'])}` so'm\n"
    await message.answer(res, parse_mode="Markdown")

@dp.message(F.text == "📊 Umumiy Statistika")
async def global_stats(message: types.Message):
    total = await db.fetchval("SELECT SUM(CASE WHEN type='add' THEN amount ELSE -amount END) FROM debts")
    await message.answer(f"📊 **JAMI HAQDORLIK:**\n\n💰 **{format_num(total or 0)}** so'm", parse_mode="Markdown")

async def main():
    await init_db()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
