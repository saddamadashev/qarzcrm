import asyncio
import sqlite3
import os
import re
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

# --- SOZLAMALAR ---
TOKEN = "7968516598:AAHRE5zJ19D0_755S3y_6-uGjW5fT0E89_M"
ADMIN_ID = 12345678  # O'zingizning ID-ingizni bu yerga yozing!

bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- YORDAMCHI FUNKSIYALAR ---
def get_uzb_time():
    return datetime.utcnow() + timedelta(hours=5)

def format_num(num):
    """1250000 -> 1 250 000 ko'rinishiga o'tkazish"""
    return f"{int(num or 0):,}".replace(",", " ")

def parse_num(text):
    """Faqat raqamlarni ajratib olish (bo'sh joy va $ ni tozalash)"""
    clean_text = re.sub(r'[^\d]', '', text)
    return float(clean_text) if clean_text else 0

# --- BAZA ---
def init_db():
    conn = sqlite3.connect('debts_safe.db')
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, name TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS clients (id INTEGER PRIMARY KEY AUTOINCREMENT, owner_id INTEGER, name TEXT, balance REAL DEFAULT 0)')
    c.execute('CREATE TABLE IF NOT EXISTS transactions (owner_id INTEGER, client_id INTEGER, amount REAL, type TEXT, date TEXT)')
    conn.commit()
    conn.close()

init_db()

class Form(StatesGroup):
    adding_client = State()
    amount_input = State()

# --- KLAVIATURALAR ---
def main_menu(user_id):
    kb = [
        [KeyboardButton(text="👥 Mijozlarim"), KeyboardButton(text="📊 Statistika")],
        [KeyboardButton(text="➕ Mijoz qo'shish"), KeyboardButton(text="📋 Hisobot (Matn)")]
    ]
    if user_id == ADMIN_ID:
        kb.append([KeyboardButton(text="👑 Admin Panel")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

# --- HANDLERLAR ---
@dp.message(Command("start"))
async def start(message: types.Message):
    conn = sqlite3.connect('debts_safe.db')
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users VALUES (?, ?)", (message.from_user.id, message.from_user.full_name))
    conn.commit()
    conn.close()
    await message.answer("🚀 **Qarz daftari botiga xush kelibsiz!**", reply_markup=main_menu(message.from_user.id), parse_mode="Markdown")

@dp.message(F.text == "➕ Mijoz qo'shish")
async def add_client(message: types.Message, state: FSMContext):
    await message.answer("👤 **Mijoz ismini kiriting:**", parse_mode="Markdown")
    await state.set_state(Form.adding_client)

@dp.message(Form.adding_client)
async def save_client(message: types.Message, state: FSMContext):
    conn = sqlite3.connect('debts_safe.db')
    c = conn.cursor()
    c.execute("INSERT INTO clients (owner_id, name) VALUES (?, ?)", (message.from_user.id, message.text))
    conn.commit()
    conn.close()
    await message.answer(f"✅ **{message.text}** qo'shildi.", reply_markup=main_menu(message.from_user.id), parse_mode="Markdown")
    await state.clear()

# --- MATNLI HISOBOT (EXCEL O'RNIGA) ---
@dp.message(F.text == "📋 Hisobot (Matn)")
async def text_report(message: types.Message):
    conn = sqlite3.connect('debts_safe.db')
    c = conn.cursor()
    c.execute("SELECT name, balance FROM clients WHERE owner_id=?", (message.from_user.id,))
    data = c.fetchall()
    conn.close()

    if not data:
        return await message.answer("Sizda hali mijozlar yo'q.")

    report = "📋 **SIZNING HISOBOTINGIZ**\n━━━━━━━━━━━━━━━\n"
    total_all = 0
    for name, bal in data:
        report += f"👤 {name}: `{format_num(bal)}` so'm\n"
        total_all += bal
    report += f"━━━━━━━━━━━━━━━\n💰 **Jami:** `{format_num(total_all)}` so'm"
    
    await message.answer(report, parse_mode="Markdown")

# --- ADMIN PANEL ---
@dp.message(F.text == "👑 Admin Panel")
async def admin_panel(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    conn = sqlite3.connect('debts_safe.db')
    c = conn.cursor()
    c.execute("""SELECT u.name, SUM(c.balance) FROM users u 
                 LEFT JOIN clients c ON u.user_id = c.owner_id GROUP BY u.user_id""")
    stats = c.fetchall()
    conn.close()

    text = "👑 **ADMIN: Barcha foydalanuvchilar**\n━━━━━━━━━━━━━━━\n"
    for name, total in stats:
        user_name = name if name else "Noma'lum"
        text += f"👤 {user_name}: `{format_num(total)}` so'm\n"
    
    await message.answer(text, parse_mode="Markdown")

# --- MIJOZLAR BILAN ISHLASH ---
@dp.message(F.text == "👥 Mijozlarim")
async def list_clients(message: types.Message):
    conn = sqlite3.connect('debts_safe.db')
    c = conn.cursor()
    c.execute("SELECT id, name, balance FROM clients WHERE owner_id=?", (message.from_user.id,))
    clients = c.fetchall()
    conn.close()
    
    if not clients:
        return await message.answer("📭 Hozircha mijozlar yo'q.")
    
    btns = [[InlineKeyboardButton(text=f"👤 {cl[1]} | {format_num(cl[2])}", callback_data=f"v_{cl[0]}")] for cl in clients]
    await message.answer("📋 **Mijozlar ro'yxati:**", reply_markup=InlineKeyboardMarkup(inline_keyboard=btns), parse_mode="Markdown")

@dp.callback_query(F.data.startswith("v_"))
async def view_client(call: types.CallbackQuery):
    c_id = call.data.split("_")[1]
    conn = sqlite3.connect('debts_safe.db')
    c = conn.cursor()
    c.execute("SELECT name, balance FROM clients WHERE id=?", (c_id,))
    cl = c.fetchone()
    conn.close()
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Qarz qo'shish", callback_data=f"a_add_{c_id}"),
         InlineKeyboardButton(text="✅ To'lov olish", callback_data=f"a_sub_{c_id}")]
    ])
    await call.message.edit_text(f"👤 Mijoz: **{cl[0]}**\n💰 Qoldiq: `{format_num(cl[1])}` so'm", 
                                 reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data.startswith("a_"))
async def action_input(call: types.CallbackQuery, state: FSMContext):
    _, mode, c_id = call.data.split("_")
    await state.update_data(c_id=c_id, mode=mode)
    text = "➕ Summani kiriting (Qarz):" if mode == 'add' else "✅ Summani kiriting (To'lov):"
    await call.message.answer(text)
    await state.set_state(Form.amount_input)

@dp.message(Form.amount_input)
async def process_amount(message: types.Message, state: FSMContext):
    data = await state.get_data()
    amt = parse_num(message.text)
    db_amt = amt if data['mode'] == 'add' else -amt
    
    conn = sqlite3.connect('debts_safe.db')
    c = conn.cursor()
    c.execute("UPDATE clients SET balance = balance + ? WHERE id = ?", (db_amt, data['c_id']))
    c.execute("SELECT name, balance FROM clients WHERE id = ?", (data['c_id'],))
    name, bal = c.fetchone()
    conn.commit()
    conn.close()
    
    await message.answer(f"✅ **Bajarildi!**\n👤 {name}\n📉 Yangi qoldiq: `{format_num(bal)}` so'm", 
                         reply_markup=main_menu(message.from_user.id), parse_mode="Markdown")
    await state.clear()

@dp.message(F.text == "📊 Statistika")
async def my_stats(message: types.Message):
    conn = sqlite3.connect('debts_safe.db')
    c = conn.cursor()
    c.execute("SELECT SUM(balance) FROM clients WHERE owner_id=?", (message.from_user.id,))
    total = c.fetchone()[0] or 0
    conn.close()
    await message.answer(f"💰 Sizdagi jami haqdorlik:\n👉 **{format_num(total)}** so'm", parse_mode="Markdown")

async def main():
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
