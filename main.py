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

# --- YORDAMCHI FUNKSIYALAR ---
def format_num(num):
    try:
        return "{:,.0f}".format(num).replace(",", " ")
    except: return "0"

def parse_num(text):
    clean_text = re.sub(r'[^\d]', '', text)
    return float(clean_text) if clean_text else 0

# --- BAZA BILAN ISHLASH (Xavfsiz ulanish) ---
async def run_query(query, *args, fetch=False, fetchrow=False, fetchval=False):
    """Har safar yangi ulanish ochib, ish bitgach yopadigan universal funksiya"""
    conn = await asyncpg.connect(DATABASE_URL.replace("postgres://", "postgresql://", 1))
    try:
        if fetch: return await conn.fetch(query, *args)
        if fetchrow: return await conn.fetchrow(query, *args)
        if fetchval: return await conn.fetchval(query, *args)
        return await conn.execute(query, *args)
    finally:
        await conn.close()

async def init_db():
    await run_query("""
        CREATE TABLE IF NOT EXISTS bot_users(user_id BIGINT PRIMARY KEY, current_client_id INTEGER);
        CREATE TABLE IF NOT EXISTS clients(id SERIAL PRIMARY KEY, owner_id BIGINT, name TEXT, UNIQUE(owner_id, name));
        CREATE TABLE IF NOT EXISTS operations(id SERIAL PRIMARY KEY, client_id INTEGER REFERENCES clients(id) ON DELETE CASCADE, amount FLOAT, op_type TEXT, created_at TIMESTAMP);
    """)
    logging.info("✅ Baza tayyor!")

# --- KLAVIATURALAR ---
def get_main_menu():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="👥 Mijozlarim"), KeyboardButton(text="➕ Mijoz qo'shish")], [KeyboardButton(text="📊 Umumiy hisobot")]], resize_keyboard=True)

def get_client_menu():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="➕ Qarz yozish"), KeyboardButton(text="➖ To'lov olish")], [KeyboardButton(text="💰 Balans"), KeyboardButton(text="📜 Tarix")], [KeyboardButton(text="⬅️ Orqaga")]], resize_keyboard=True)

# --- HANDLERLAR ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await run_query("INSERT INTO bot_users(user_id) VALUES($1) ON CONFLICT DO NOTHING", message.from_user.id)
    await message.answer("🚀 **Super Qarz CRM tizimi ishga tushdi!**", reply_markup=get_main_menu(), parse_mode="Markdown")

@dp.message(F.text == "➕ Mijoz qo'shish")
async def start_add_client(message: types.Message):
    state_data[message.from_user.id] = "waiting_name"
    await message.answer("👤 **Ismini kiriting:**", reply_markup=ReplyKeyboardRemove(), parse_mode="Markdown")

@dp.message(lambda m: state_data.get(m.from_user.id) == "waiting_name")
async def save_client(message: types.Message):
    try:
        await run_query("INSERT INTO clients(owner_id, name) VALUES($1, $2)", message.from_user.id, message.text.strip())
        await message.answer(f"✅ **{message.text}** qo'shildi!", reply_markup=get_main_menu(), parse_mode="Markdown")
    except:
        await message.answer("❌ Bu ismdagi mijoz bazada bor.")
    state_data.pop(message.from_user.id, None)

@dp.message(F.text == "👥 Mijozlarim")
async def show_clients(message: types.Message):
    rows = await run_query("SELECT name FROM clients WHERE owner_id=$1 ORDER BY name", message.from_user.id, fetch=True)
    if not rows: return await message.answer("📭 Bo'sh.")
    kb = [[KeyboardButton(text=r['name'])] for r in rows]
    kb.append([KeyboardButton(text="⬅️ Bosh menyu")])
    await message.answer("👇 **Tanlang:**", reply_markup=ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True), parse_mode="Markdown")

@dp.message(F.text.in_(["➕ Qarz yozish", "➖ To'lov olish"]))
async def ask_amount(message: types.Message):
    c_id = await run_query("SELECT current_client_id FROM bot_users WHERE user_id=$1", message.from_user.id, fetchval=True)
    if not c_id: return await message.answer("⚠️ Avval mijozni tanlang!")
    state_data[message.from_user.id] = "plus" if "➕" in message.text else "minus"
    await message.answer("💰 **Summani kiriting:**", reply_markup=ReplyKeyboardRemove(), parse_mode="Markdown")

@dp.message(lambda m: state_data.get(m.from_user.id) in ["plus", "minus"])
async def process_op(message: types.Message):
    user_id = message.from_user.id
    mode = state_data[user_id]
    amount = parse_num(message.text)
    if amount <= 0: return await message.answer("❌ Raqam kiriting.")

    c_id = await run_query("SELECT current_client_id FROM bot_users WHERE user_id=$1", user_id, fetchval=True)
    now = datetime.now(tz)
    await run_query("INSERT INTO operations(client_id, amount, op_type, created_at) VALUES($1, $2, $3, $4)", c_id, amount, mode, now)
    
    name = await run_query("SELECT name FROM clients WHERE id=$1", c_id, fetchval=True)
    plus = await run_query("SELECT COALESCE(SUM(amount),0) FROM operations WHERE client_id=$1 AND op_type='plus'", c_id, fetchval=True)
    minus = await run_query("SELECT COALESCE(SUM(amount),0) FROM operations WHERE client_id=$1 AND op_type='minus'", c_id, fetchval=True)
    
    state_data.pop(user_id, None)
    receipt = f"🧾 **AMALIYOT**\n👤: **{name}**\n💰: `{format_num(amount)}` so'm\n📉 Qoldiq: **{format_num(plus-minus)}** so'm"
    await message.answer(receipt, reply_markup=get_client_menu(), parse_mode="Markdown")

@dp.message(F.text == "💰 Balans")
async def check_balance(message: types.Message):
    c_id = await run_query("SELECT current_client_id FROM bot_users WHERE user_id=$1", message.from_user.id, fetchval=True)
    if not c_id: return
    plus = await run_query("SELECT COALESCE(SUM(amount),0) FROM operations WHERE client_id=$1 AND op_type='plus'", c_id, fetchval=True)
    minus = await run_query("SELECT COALESCE(SUM(amount),0) FROM operations WHERE client_id=$1 AND op_type='minus'", c_id, fetchval=True)
    await message.answer(f"💰 Qoldiq: **{format_num(plus-minus)}** so'm", parse_mode="Markdown")

@dp.message(F.text == "📜 Tarix")
async def show_history(message: types.Message):
    c_id = await run_query("SELECT current_client_id FROM bot_users WHERE user_id=$1", message.from_user.id, fetchval=True)
    rows = await run_query("SELECT * FROM operations WHERE client_id=$1 ORDER BY created_at DESC LIMIT 10", c_id, fetch=True)
    res = "📜 **Tarix:**\n\n"
    for r in rows:
        res += f"`{r['created_at'].strftime('%d.%m %H:%M')}` | {'➕' if r['op_type']=='plus' else '➖'} `{format_num(r['amount'])}` so'm\n"
    await message.answer(res, parse_mode="Markdown")

@dp.message(F.text == "⬅️ Bosh menyu")
@dp.message(F.text == "⬅️ Orqaga")
async def back(message: types.Message):
    await run_query("UPDATE bot_users SET current_client_id = NULL WHERE user_id=$1", message.from_user.id)
    await message.answer("🏠 Menyu", reply_markup=get_main_menu())

@dp.message()
async def select_client(message: types.Message):
    row = await run_query("SELECT id, name FROM clients WHERE owner_id=$1 AND name=$2", message.from_user.id, message.text, fetchrow=True)
    if row:
        await run_query("UPDATE bot_users SET current_client_id = $1 WHERE user_id=$2", row['id'], message.from_user.id)
        await message.answer(f"✅ **{row['name']}** tanlandi.", reply_markup=get_client_menu(), parse_mode="Markdown")

async def main():
    await init_db()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
