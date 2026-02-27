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
BOT_TOKEN = os.getenv("BOT_TOKEN", "7968516598:AAHRE5zJ19D0_755S3y_6-uGjW5fT0E89_M")
DATABASE_URL = os.getenv("DATABASE_URL")

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
tz = pytz.timezone("Asia/Tashkent")
state_data = {}

# Pool ob'ekti global saqlanadi
db_pool = None

# --- YORDAMCHI FUNKSIYALAR ---
def format_num(num):
    try:
        return "{:,.0f}".format(num or 0).replace(",", " ")
    except: return "0"

def parse_num(text):
    clean_text = re.sub(r'[^\d]', '', text)
    return float(clean_text) if clean_text else 0

# --- BAZA BILAN ISHLASH (Professional Pool) ---
async def get_db_pool():
    global db_pool
    if db_pool is None:
        url = DATABASE_URL.replace("postgres://", "postgresql://", 1)
        db_pool = await asyncpg.create_pool(
            url,
            min_size=1,
            max_size=10,
            max_queries=1000,
            max_inactive_connection_lifetime=60
        )
    return db_pool

# --- HANDLERLAR ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    pool = await get_db_pool()
    async with pool.acquire() as db:
        await db.execute("INSERT INTO bot_users(user_id) VALUES($1) ON CONFLICT DO NOTHING", message.from_user.id)
    
    kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="👥 Mijozlarim"), KeyboardButton(text="➕ Mijoz qo'shish")],
        [KeyboardButton(text="📊 Umumiy hisobot")]
    ], resize_keyboard=True)
    
    await message.answer("🚀 **Super Qarz CRM tizimi ishga tushdi!**", reply_markup=kb, parse_mode="Markdown")

@dp.message(F.text == "➕ Mijoz qo'shish")
async def start_add_client(message: types.Message):
    state_data[message.from_user.id] = "waiting_name"
    await message.answer("👤 **Ismini kiriting:**", reply_markup=ReplyKeyboardRemove(), parse_mode="Markdown")

@dp.message(lambda m: state_data.get(m.from_user.id) == "waiting_name")
async def save_client(message: types.Message):
    user_id = message.from_user.id
    name = message.text.strip()
    pool = await get_db_pool()
    try:
        async with pool.acquire() as db:
            await db.execute("INSERT INTO clients(owner_id, name) VALUES($1, $2)", user_id, name)
        await message.answer(f"✅ **{name}** qo'shildi!", reply_markup=cmd_start_kb()) # Qisqartma uchun
    except:
        await message.answer("❌ Bu ismdagi mijoz bor.")
    state_data.pop(user_id, None)

@dp.message(F.text == "👥 Mijozlarim")
async def show_clients(message: types.Message):
    pool = await get_db_pool()
    async with pool.acquire() as db:
        rows = await db.fetch("SELECT name FROM clients WHERE owner_id=$1 ORDER BY name", message.from_user.id)
    
    if not rows: return await message.answer("📭 Bo'sh.")
    kb = [[KeyboardButton(text=r['name'])] for r in rows]
    kb.append([KeyboardButton(text="⬅️ Bosh menyu")])
    await message.answer("👇 **Tanlang:**", reply_markup=ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True), parse_mode="Markdown")

@dp.message(F.text.in_(["➕ Qarz yozish", "➖ To'lov olish"]))
async def ask_amount(message: types.Message):
    pool = await get_db_pool()
    async with pool.acquire() as db:
        c_id = await db.fetchval("SELECT current_client_id FROM bot_users WHERE user_id=$1", message.from_user.id)
    
    if not c_id: return await message.answer("⚠️ Avval mijozni tanlang!")
    state_data[message.from_user.id] = "plus" if "➕" in message.text else "minus"
    await message.answer("💰 **Summani kiriting:**", reply_markup=ReplyKeyboardRemove(), parse_mode="Markdown")

@dp.message(lambda m: state_data.get(m.from_user.id) in ["plus", "minus"])
async def process_op(message: types.Message):
    user_id = message.from_user.id
    mode = state_data[user_id]
    amount = parse_num(message.text)
    if amount <= 0: return await message.answer("❌ Raqam kiriting.")

    pool = await get_db_pool()
    async with pool.acquire() as db:
        c_id = await db.fetchval("SELECT current_client_id FROM bot_users WHERE user_id=$1", user_id)
        now = datetime.now(tz)
        await db.execute("INSERT INTO operations(client_id, amount, op_type, created_at) VALUES($1, $2, $3, $4)", c_id, amount, mode, now)
        
        name = await db.fetchval("SELECT name FROM clients WHERE id=$1", c_id)
        p = await db.fetchval("SELECT COALESCE(SUM(amount),0) FROM operations WHERE client_id=$1 AND op_type='plus'", c_id)
        m = await db.fetchval("SELECT COALESCE(SUM(amount),0) FROM operations WHERE client_id=$1 AND op_type='minus'", c_id)
    
    state_data.pop(user_id, None)
    res = f"🧾 **AMALIYOT**\n👤: **{name}**\n💰: `{format_num(amount)}` so'm\n📉 Qoldiq: **{format_num(p-m)}** so'm"
    
    kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="➕ Qarz yozish"), KeyboardButton(text="➖ To'lov olish")],
        [KeyboardButton(text="💰 Balans"), KeyboardButton(text="📜 Tarix")],
        [KeyboardButton(text="⬅️ Orqaga")]
    ], resize_keyboard=True)
    
    await message.answer(res, reply_markup=kb, parse_mode="Markdown")

@dp.message(F.text == "💰 Balans")
async def check_balance(message: types.Message):
    pool = await get_db_pool()
    async with pool.acquire() as db:
        c_id = await db.fetchval("SELECT current_client_id FROM bot_users WHERE user_id=$1", message.from_user.id)
        p = await db.fetchval("SELECT COALESCE(SUM(amount),0) FROM operations WHERE client_id=$1 AND op_type='plus'", c_id)
        m = await db.fetchval("SELECT COALESCE(SUM(amount),0) FROM operations WHERE client_id=$1 AND op_type='minus'", c_id)
    await message.answer(f"💰 Qoldiq: **{format_num(p-m)}** so'm", parse_mode="Markdown")

@dp.message(F.text == "⬅️ Orqaga")
async def back(message: types.Message):
    pool = await get_db_pool()
    async with pool.acquire() as db:
        await db.execute("UPDATE bot_users SET current_client_id = NULL WHERE user_id=$1", message.from_user.id)
    
    kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="👥 Mijozlarim"), KeyboardButton(text="➕ Mijoz qo'shish")],
        [KeyboardButton(text="📊 Umumiy hisobot")]
    ], resize_keyboard=True)
    await message.answer("🏠 Menyu", reply_markup=kb)

@dp.message()
async def select_client(message: types.Message):
    pool = await get_db_pool()
    async with pool.acquire() as db:
        row = await db.fetchrow("SELECT id, name FROM clients WHERE owner_id=$1 AND name=$2", message.from_user.id, message.text)
        if row:
            await db.execute("UPDATE bot_users SET current_client_id = $1 WHERE user_id=$2", row['id'], message.from_user.id)
            
            kb = ReplyKeyboardMarkup(keyboard=[
                [KeyboardButton(text="➕ Qarz yozish"), KeyboardButton(text="➖ To'lov olish")],
                [KeyboardButton(text="💰 Balans"), KeyboardButton(text="📜 Tarix")],
                [KeyboardButton(text="⬅️ Orqaga")]
            ], resize_keyboard=True)
            await message.answer(f"✅ **{row['name']}** tanlandi.", reply_markup=kb, parse_mode="Markdown")

# --- BOTNI ISHGA TUSHIRISH ---
async def main():
    pool = await get_db_pool()
    async with pool.acquire() as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS bot_users(user_id BIGINT PRIMARY KEY, current_client_id INTEGER);
            CREATE TABLE IF NOT EXISTS clients(id SERIAL PRIMARY KEY, owner_id BIGINT, name TEXT, UNIQUE(owner_id, name));
            CREATE TABLE IF NOT EXISTS operations(id SERIAL PRIMARY KEY, client_id INTEGER REFERENCES clients(id) ON DELETE CASCADE, amount FLOAT, op_type TEXT, created_at TIMESTAMP);
        """)
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
