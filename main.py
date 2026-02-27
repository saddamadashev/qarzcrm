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
# Railway-da BOT_TOKEN va DATABASE_URL ni Variable-ga qo'shgan bo'lishingiz shart
BOT_TOKEN = os.getenv("BOT_TOKEN", "8759158410:AAFH4Lz-1VsndTC4VRABU7uHYU-qCFoY60Q")
DATABASE_URL = os.getenv("DATABASE_URL")

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

tz = pytz.timezone("Asia/Tashkent")
state_data = {} # Vaqtinchalik holat uchun

# --- YORDAMCHI FUNKSIYALAR ---
def format_num(num):
    """Raqamlarni 5 000 000 ko'rinishida formatlash"""
    try:
        return "{:,.0f}".format(num).replace(",", " ")
    except:
        return "0"

def parse_num(text):
    """Matndan faqat sonlarni ajratib olish (probel yoki $ bo'lsa ham)"""
    clean_text = re.sub(r'[^\d]', '', text)
    return float(clean_text) if clean_text else 0

# --- BAZA BILAN ISHLASH (PostgreSQL) ---
async def init_db():
    global conn_pool
    conn_pool = await asyncpg.create_pool(DATABASE_URL)
    
    async with conn_pool.acquire() as db:
        # Foydalanuvchi qaysi mijoz ustida ishlayotganini saqlash
        await db.execute("""
        CREATE TABLE IF NOT EXISTS bot_users(
            user_id BIGINT PRIMARY KEY,
            current_client_id INTEGER
        )
        """)
        
        # Mijozlar jadvali
        await db.execute("""
        CREATE TABLE IF NOT EXISTS clients(
            id SERIAL PRIMARY KEY,
            owner_id BIGINT,
            name TEXT,
            UNIQUE(owner_id, name)
        )
        """)
        
        # Qarzlar va To'lovlar (Xotira o'chmaydi)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS operations(
            id SERIAL PRIMARY KEY,
            client_id INTEGER REFERENCES clients(id) ON DELETE CASCADE,
            amount FLOAT,
            op_type TEXT, -- 'plus' yoki 'minus'
            created_at TIMESTAMP
        )
        """)

# --- KLAVIATURALAR ---
def get_main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👥 Mijozlarim"), KeyboardButton(text="➕ Mijoz qo'shish")],
            [KeyboardButton(text="📊 Umumiy hisobot")]
        ],
        resize_keyboard=True
    )

def get_client_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Qarz yozish"), KeyboardButton(text="➖ To'lov olish")],
            [KeyboardButton(text="💰 Balans"), KeyboardButton(text="📜 Tarix")],
            [KeyboardButton(text="⬅️ Orqaga")]
        ],
        resize_keyboard=True
    )

# --- HANDLERLAR ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    async with conn_pool.acquire() as db:
        await db.execute("INSERT INTO bot_users(user_id) VALUES($1) ON CONFLICT DO NOTHING", message.from_user.id)
    await message.answer("🚀 **Super Qarz CRM tizimiga xush kelibsiz!**", reply_markup=get_main_menu(), parse_mode="Markdown")

@dp.message(F.text == "➕ Mijoz qo'shish")
async def start_add_client(message: types.Message):
    state_data[message.from_user.id] = "waiting_client_name"
    await message.answer("👤 **Yangi mijoz ismini kiriting:**", reply_markup=ReplyKeyboardRemove(), parse_mode="Markdown")

@dp.message(lambda m: state_data.get(m.from_user.id) == "waiting_client_name")
async def save_new_client(message: types.Message):
    user_id = message.from_user.id
    name = message.text.strip()
    
    async with conn_pool.acquire() as db:
        try:
            await db.execute("INSERT INTO clients(owner_id, name) VALUES($1, $2)", user_id, name)
            await message.answer(f"✅ **{name}** ro'yxatga olindi!", reply_markup=get_main_menu(), parse_mode="Markdown")
        except asyncpg.UniqueViolationError:
            await message.answer("❌ Bu ismdagi mijoz sizda allaqachon bor.")
    state_data.pop(user_id, None)

@dp.message(F.text == "👥 Mijozlarim")
async def show_clients(message: types.Message):
    async with conn_pool.acquire() as db:
        rows = await db.fetch("SELECT name FROM clients WHERE owner_id=$1 ORDER BY name", message.from_user.id)
    
    if not rows:
        return await message.answer("📭 Mijozlar ro'yxati bo'sh.")
    
    kb = [[KeyboardButton(text=r['name'])] for r in rows]
    kb.append([KeyboardButton(text="⬅️ Bosh menyu")])
    await message.answer("👇 **Mijozni tanlang:**", reply_markup=ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True), parse_mode="Markdown")

@dp.message(F.text == "⬅️ Bosh menyu")
@dp.message(F.text == "⬅️ Orqaga")
async def back_to_home(message: types.Message):
    async with conn_pool.acquire() as db:
        await db.execute("UPDATE bot_users SET current_client_id = NULL WHERE user_id = $1", message.from_user.id)
    await message.answer("🏠 **Asosiy menyu**", reply_markup=get_main_menu(), parse_mode="Markdown")

# --- AMALIYOTLAR (Mijoz ichidagi funksiyalar) ---

@dp.message(F.text.in_(["➕ Qarz yozish", "➖ To'lov olish"]))
async def ask_amount(message: types.Message):
    async with conn_pool.acquire() as db:
        curr_id = await db.fetchval("SELECT current_client_id FROM bot_users WHERE user_id = $1", message.from_user.id)
    
    if not curr_id:
        return await message.answer("⚠️ Avval mijozni tanlang!")

    state_data[message.from_user.id] = "plus" if "➕" in message.text else "minus"
    await message.answer("💰 **Summani kiriting:**\n_(Masalan: 2 500 000)_", reply_markup=ReplyKeyboardRemove(), parse_mode="Markdown")

@dp.message(lambda m: state_data.get(m.from_user.id) in ["plus", "minus"])
async def process_op(message: types.Message):
    user_id = message.from_user.id
    mode = state_data[user_id]
    amount = parse_num(message.text)
    
    if amount <= 0:
        return await message.answer("❌ Xato! Iltimos, faqat raqam kiriting.")

    async with conn_pool.acquire() as db:
        client_id = await db.fetchval("SELECT current_client_id FROM bot_users WHERE user_id = $1", user_id)
        now = datetime.now(tz)
        
        # Amaliyotni saqlash
        await db.execute("INSERT INTO operations(client_id, amount, op_type, created_at) VALUES($1, $2, $3, $4)", 
                         client_id, amount, mode, now)
        
        # Yangi hisob-kitob
        client_info = await db.fetchrow("SELECT name FROM clients WHERE id=$1", client_id)
        total_plus = await db.fetchval("SELECT COALESCE(SUM(amount),0) FROM operations WHERE client_id=$1 AND op_type='plus'", client_id)
        total_minus = await db.fetchval("SELECT COALESCE(SUM(amount),0) FROM operations WHERE client_id=$1 AND op_type='minus'", client_id)
        balance = total_plus - total_minus

    # CHIROYLI CHEK
    status = "Qarz qo'shildi ➕" if mode == "plus" else "To'lov qilindi ✅"
    receipt = (
        f"📋 **AMALIYOT CHEKI**\n"
        f"━━━━━━━━━━━━━━━\n"
        f"👤 Mijoz: **{client_info['name']}**\n"
        f"📅 Sana: `{now.strftime('%d.%m.%Y')}`\n"
        f"⏰ Vaqt: `{now.strftime('%H:%M:%S')}`\n"
        f"━━━━━━━━━━━━━━━\n"
        f"💰 Miqdor: `{format_num(amount)}` so'm\n"
        f"📝 Holat: {status}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📉 Qoldiq: **{format_num(balance)}** so'm"
    )
    
    state_data.pop(user_id, None)
    await message.answer(receipt, reply_markup=get_client_menu(), parse_mode="Markdown")

@dp.message(F.text == "💰 Balans")
async def check_balance(message: types.Message):
    async with conn_pool.acquire() as db:
        c_id = await db.fetchval("SELECT current_client_id FROM bot_users WHERE user_id = $1", message.from_user.id)
        if not c_id: return
        
        plus = await db.fetchval("SELECT COALESCE(SUM(amount),0) FROM operations WHERE client_id=$1 AND op_type='plus'", c_id)
        minus = await db.fetchval("SELECT COALESCE(SUM(amount),0) FROM operations WHERE client_id=$1 AND op_type='minus'", c_id)
        name = await db.fetchval("SELECT name FROM clients WHERE id=$1", c_id)
        
    await message.answer(f"👤 Mijoz: **{name}**\n💰 Joriy qarz: **{format_num(plus-minus)}** so'm", parse_mode="Markdown")

@dp.message(F.text == "📜 Tarix")
async def show_history(message: types.Message):
    async with conn_pool.acquire() as db:
        c_id = await db.fetchval("SELECT current_client_id FROM bot_users WHERE user_id = $1", message.from_user.id)
        rows = await db.fetch("SELECT * FROM operations WHERE client_id=$1 ORDER BY created_at DESC LIMIT 10", c_id)
    
    if not rows: return await message.answer("Tarix mavjud emas.")
    
    res = "📜 **SO'NGGI 10 TA AMALIYOT:**\n\n"
    for r in rows:
        sign = "➕" if r['op_type'] == 'plus' else "➖"
        res += f"`{r['created_at'].strftime('%d.%m %H:%M')}` | {sign} `{format_num(r['amount'])}` so'm\n"
    await message.answer(res, parse_mode="Markdown")

@dp.message(F.text == "📊 Umumiy hisobot")
async def total_stats(message: types.Message):
    async with conn_pool.acquire() as db:
        total = await db.fetchval("""
            SELECT SUM(CASE WHEN op_type='plus' THEN amount ELSE -amount END) 
            FROM operations o JOIN clients c ON o.client_id = c.id 
            WHERE c.owner_id = $1
        """, message.from_user.id)
        
    await message.answer(f"📊 **SIZNING UMUMIY HAQDORLIGINGIZ:**\n\n💰 **{format_num(total or 0)}** so'm", parse_mode="Markdown")

# --- MIJOZNI TANLASH (Eng oxirgi handler bo'lishi kerak) ---
@dp.message()
async def client_selector(message: types.Message):
    async with conn_pool.acquire() as db:
        row = await db.fetchrow("SELECT id, name FROM clients WHERE owner_id=$1 AND name=$2", message.from_user.id, message.text)
        if row:
            await db.execute("UPDATE bot_users SET current_client_id = $1 WHERE user_id = $2", row['id'], message.from_user.id)
            await message.answer(f"✅ **{row['name']}** tanlandi. Amaliyotni tanlang:", reply_markup=get_client_menu(), parse_mode="Markdown")

async def main():
    await init_db()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
