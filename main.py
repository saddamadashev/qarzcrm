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

# Global o'zgaruvchilar
db = None
state = {}
current_client = {}
tz = pytz.timezone("Asia/Tashkent")

# --- YORDAMCHI FUNKSIYALAR ---
def format_num(num):
    """5000000 -> 5 000 000 ko'rinishiga o'tkazish"""
    try:
        return "{:,.0f}".format(num).replace(",", " ")
    except:
        return "0"

def parse_num(text):
    """Matndan faqat raqamlarni ajratib olish"""
    clean_text = re.sub(r'[^\d]', '', text)
    return float(clean_text) if clean_text else 0

# --- BAZA BILAN ISHLASH ---
async def init_db():
    global db
    db = await asyncpg.connect(DATABASE_URL)
    
    # Mijozlar jadvali
    await db.execute("""
    CREATE TABLE IF NOT EXISTS clients(
        id SERIAL PRIMARY KEY,
        name TEXT UNIQUE
    )
    """)
    # Qarzlar va To'lovlar tarixi (Xotiradan o'chmaydi)
    await db.execute("""
    CREATE TABLE IF NOT EXISTS debts(
        id SERIAL PRIMARY KEY,
        client_id INTEGER REFERENCES clients(id),
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
    await message.answer("🏦 Qarz CRM tizimiga xush kelibsiz!", reply_markup=main_menu())

@dp.message(F.text == "➕ Mijoz qo'shish")
async def add_client(message: types.Message):
    state[message.from_user.id] = "add_client"
    await message.answer("👤 Yangi mijoz ismini yozing:", reply_markup=ReplyKeyboardRemove())

@dp.message(lambda m: state.get(m.from_user.id) == "add_client")
async def save_client(message: types.Message):
    try:
        await db.execute("INSERT INTO clients(name) VALUES($1)", message.text)
        await message.answer(f"✅ {message.text} muvaffaqiyatli qo'shildi.", reply_markup=main_menu())
    except asyncpg.UniqueViolationError:
        await message.answer("❌ Bu ismdagi mijoz allaqachon mavjud.")
    
    state.pop(message.from_user.id, None)

@dp.message(F.text == "👥 Mijozlar")
async def list_clients(message: types.Message):
    rows = await db.fetch("SELECT * FROM clients")
    if not rows:
        return await message.answer("Hozircha mijozlar yo'q.")
    
    kb = []
    for r in rows:
        kb.append([KeyboardButton(text=r["name"])])
    kb.append([KeyboardButton(text="⬅️ Orqaga")])
    
    await message.answer("Mijozni tanlang:", reply_markup=ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True))

@dp.message(F.text == "⬅️ Orqaga")
async def go_back(message: types.Message):
    await message.answer("Asosiy menu", reply_markup=main_menu())

# Mijoz tanlanganda
@dp.message(lambda m: state.get(m.from_user.id) is None and m.text not in ["➕ Mijoz qo'shish", "👥 Mijozlar", "📊 Umumiy Statistika"])
async def select_client(message: types.Message):
    row = await db.fetchrow("SELECT * FROM clients WHERE name=$1", message.text)
    if row:
        current_client[message.from_user.id] = row["id"]
        await message.answer(f"👤 Mijoz: **{row['name']}** tanlandi.", reply_markup=client_menu(), parse_mode="Markdown")

# Qarz qo'shish yoki ayirishni boshlash
@dp.message(F.text.in_(["➕ Qarz qo'shish", "➖ Qarz ayirish"]))
async def ask_amount(message: types.Message):
    mode = "add_debt" if message.text == "➕ Qarz qo'shish" else "minus_debt"
    state[message.from_user.id] = mode
    await message.answer("💰 Summani kiriting:\n(Masalan: 5 000 000 yoki 5000000)", reply_markup=ReplyKeyboardRemove())

# Summani saqlash va Chek chiqarish
@dp.message(lambda m: state.get(m.from_user.id) in ["add_debt", "minus_debt"])
async def save_transaction(message: types.Message):
    user_id = message.from_user.id
    mode = state[user_id]
    amount = parse_num(message.text)
    
    if amount <= 0:
        return await message.answer("❌ Iltimos, to'g'ri summa kiriting.")

    client_id = current_client.get(user_id)
    type_label = "add" if mode == "add_debt" else "minus"
    now = datetime.now(tz)

    # Bazaga yozish
    await db.execute(
        "INSERT INTO debts(client_id, amount, type, created) VALUES($1, $2, $3, $4)",
        client_id, amount, type_label, now
    )

    # Yangi balansni hisoblash
    client_name = await db.fetchval("SELECT name FROM clients WHERE id=$1", client_id)
    total_add = await db.fetchval("SELECT COALESCE(SUM(amount),0) FROM debts WHERE client_id=$1 AND type='add'", client_id)
    total_minus = await db.fetchval("SELECT COALESCE(SUM(amount),0) FROM debts WHERE client_id=$1 AND type='minus'", client_id)
    new_balance = total_add - total_minus

    # CHIROYLI CHEK
    status_icon = "➕" if type_label == "add" else "➖"
    status_text = "Qarz yozildi" if type_label == "add" else "To'lov qilindi"
    
    receipt = (
        f"🧾 **AMALIYOT TASDIQLANDI**\n"
        f"━━━━━━━━━━━━━━━\n"
        f"👤 Mijoz: **{client_name}**\n"
        f"🕒 Sana: `{now.strftime('%d.%m.%Y')}`\n"
        f"⏰ Vaqt: `{now.strftime('%H:%M:%S')}`\n"
        f"━━━━━━━━━━━━━━━\n"
        f"{status_icon} Miqdor: `{format_num(amount)}` so'm\n"
        f"📝 Turi: {status_text}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📉 Qoldiq qarz: **{format_num(new_balance)}** so'm"
    )

    state.pop(user_id, None)
    await message.answer(receipt, reply_markup=client_menu(), parse_mode="Markdown")

@dp.message(F.text == "💰 Balansni ko'rish")
async def show_balance(message: types.Message):
    client_id = current_client.get(message.from_user.id)
    add = await db.fetchval("SELECT COALESCE(SUM(amount),0) FROM debts WHERE client_id=$1 AND type='add'", client_id)
    minus = await db.fetchval("SELECT COALESCE(SUM(amount),0) FROM debts WHERE client_id=$1 AND type='minus'", client_id)
    await message.answer(f"💰 Joriy umumiy qarz: **{format_num(add-minus)}** so'm", parse_mode="Markdown")

@dp.message(F.text == "📜 Tarix")
async def show_history(message: types.Message):
    client_id = current_client.get(message.from_user.id)
    rows = await db.fetch("SELECT * FROM debts WHERE client_id=$1 ORDER BY created DESC LIMIT 15", client_id)
    
    if not rows:
        return await message.answer("Ushbu mijoz bo'yicha tarix mavjud emas.")

    text = "📜 **SO'NGGI AMALIYOTLAR:**\n\n"
    for r in rows:
        sign = "➕" if r["type"] == "add" else "➖"
        date = r["created"].strftime("%d.%m.%Y %H:%M")
        text += f"▫️ `{date}` | {sign} `{format_num(r['amount'])}` so'm\n"
    
    await message.answer(text, parse_mode="Markdown")

@dp.message(F.text == "📊 Umumiy Statistika")
async def global_stats(message: types.Message):
    total = await db.fetchval("""
        SELECT COALESCE(SUM(CASE WHEN type='add' THEN amount ELSE -amount END), 0) FROM debts
    """)
    await message.answer(f"📊 **Hamma mijozlardan jami haqdorlik:**\n\n💰 **{format_num(total)}** so'm", parse_mode="Markdown")

async def main():
    await init_db()
    # Conflict xatosini oldini olish
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
