import asyncio
import sqlite3
import os
import re
import pandas as pd
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, FSInputFile

# --- SOZLAMALAR ---
TOKEN = "7968516598:AAHRE5zJ19D0_755S3y_6-uGjW5fT0E89_M"
ADMIN_ID = 565876427  # BU YERGA O'ZINGIZNING TELEGRAM ID-INGIZNI YOZING!

bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- YORDAMCHI FUNKSIYALAR ---
def get_uzb_time():
    return datetime.utcnow() + timedelta(hours=5)

def format_num(num):
    try:
        return f"{int(num):,}".replace(",", " ")
    except:
        return "0"

def parse_num(text):
    clean_text = re.sub(r'[^\d]', '', text)
    return float(clean_text) if clean_text else 0

# --- BAZA ---
def init_db():
    conn = sqlite3.connect('debts_v2.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (user_id INTEGER PRIMARY KEY, username TEXT, joined_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS clients 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, owner_id INTEGER, name TEXT, balance REAL DEFAULT 0, last_update TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS transactions 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, owner_id INTEGER, client_id INTEGER, amount REAL, type TEXT, date TEXT)''')
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
        [KeyboardButton(text="➕ Mijoz qo'shish"), KeyboardButton(text="📁 Excel Hisobot")]
    ]
    if user_id == ADMIN_ID:
        kb.append([KeyboardButton(text="👑 Admin Panel")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

# --- HANDLERLAR ---
@dp.message(Command("start"))
async def start(message: types.Message):
    conn = sqlite3.connect('debts_v2.db')
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, username, joined_at) VALUES (?, ?, ?)", 
              (message.from_user.id, message.from_user.full_name, get_uzb_time().strftime("%Y-%m-%d")))
    conn.commit()
    conn.close()
    await message.answer(f"Xush kelibsiz, {message.from_user.first_name}!\nSizning shaxsiy qarz daftaringiz tayyor.", 
                         reply_markup=main_menu(message.from_user.id))

@dp.message(F.text == "➕ Mijoz qo'shish")
async def add_client(message: types.Message, state: FSMContext):
    await message.answer("👤 **Mijoz ismini kiriting:**", parse_mode="Markdown")
    await state.set_state(Form.adding_client)

@dp.message(Form.adding_client)
async def save_client(message: types.Message, state: FSMContext):
    conn = sqlite3.connect('debts_v2.db')
    c = conn.cursor()
    c.execute("INSERT INTO clients (owner_id, name, last_update) VALUES (?, ?, ?)", 
              (message.from_user.id, message.text, get_uzb_time().strftime("%Y-%m-%d")))
    conn.commit()
    conn.close()
    await message.answer(f"✅ **{message.text}** qo'shildi.", reply_markup=main_menu(message.from_user.id), parse_mode="Markdown")
    await state.clear()

# --- EXCEL VA HISOBOT ---
@dp.message(F.text == "📁 Excel Hisobot")
async def report_menu(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Oylik Excel", callback_data="ex_month"),
         InlineKeyboardButton(text="📆 Yillik Excel", callback_data="ex_year")]
    ])
    await message.answer("Qaysi davr uchun Excel hisobot kerak?", reply_markup=kb)

@dp.callback_query(F.data.startswith("ex_"))
async def generate_excel(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    period = callback.data.split("_")[1]
    
    conn = sqlite3.connect('debts_v2.db')
    query = f"SELECT name as 'Mijoz', balance as 'Qarz miqdori', last_update as 'Oxirgi yangilanish' FROM clients WHERE owner_id={user_id}"
    df = pd.read_sql_query(query, conn)
    conn.close()

    if df.empty:
        await callback.answer("Ma'lumot topilmadi.", show_alert=True)
        return

    file_name = f"Hisobot_{user_id}_{period}.xlsx"
    df.to_excel(file_name, index=False)
    
    file = FSInputFile(file_name)
    await callback.message.answer_document(file, caption=f"📊 Sizning {period}lik hisobotingiz tayyor.")
    os.remove(file_name)

# --- ADMIN PANEL ---
@dp.message(F.text == "👑 Admin Panel")
async def admin_panel(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    conn = sqlite3.connect('debts_v2.db')
    c = conn.cursor()
    # Barcha foydalanuvchilarning jami qarzlarini hisoblash
    c.execute("""SELECT u.username, SUM(c.balance), u.user_id 
                 FROM users u LEFT JOIN clients c ON u.user_id = c.owner_id 
                 GROUP BY u.user_id""")
    stats = c.fetchall()
    conn.close()

    text = "📊 **Barcha foydalanuvchilar holati:**\n\n"
    for s in stats:
        name = s[0] if s[0] else "Noma'lum"
        total = s[1] if s[1] else 0
        text += f"👤 {name}: `{format_num(total)}` so'm\n"

    await message.answer(text, parse_mode="Markdown")

# --- MIJOZLAR VA AMALIYOTLAR (AVVALGI IDEAL VERSIYA) ---
@dp.message(F.text == "👥 Mijozlarim")
async def list_clients(message: types.Message):
    conn = sqlite3.connect('debts_v2.db')
    c = conn.cursor()
    c.execute("SELECT id, name, balance FROM clients WHERE owner_id=?", (message.from_user.id,))
    clients = c.fetchall()
    conn.close()
    
    if not clients:
        await message.answer("📭 Mijozlar yo'q.")
        return
    
    buttons = [[InlineKeyboardButton(text=f"{cl[1]} | {format_num(cl[2])}", callback_data=f"view_{cl[0]}")] for cl in clients]
    await message.answer("📋 Mijozlaringiz:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@dp.callback_query(F.data.startswith("view_"))
async def view_client(callback: types.CallbackQuery):
    c_id = callback.data.split("_")[1]
    conn = sqlite3.connect('debts_v2.db')
    c = conn.cursor()
    c.execute("SELECT name, balance FROM clients WHERE id=?", (c_id,))
    cl = c.fetchone()
    conn.close()
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Qarz qo'shish", callback_data=f"act_add_{c_id}"),
         InlineKeyboardButton(text="✅ To'lov olish", callback_data=f"act_sub_{c_id}")]
    ])
    await callback.message.edit_text(f"👤 Mijoz: **{cl[0]}**\n💰 Qarz: `{format_num(cl[1])}` so'm", 
                                     reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data.startswith("act_"))
async def action(callback: types.CallbackQuery, state: FSMContext):
    _, mode, c_id = callback.data.split("_")
    await state.update_data(c_id=c_id, mode=mode)
    await callback.message.answer("Summani kiriting:")
    await state.set_state(Form.amount_input)

@dp.message(Form.amount_input)
async def process_amount(message: types.Message, state: FSMContext):
    data = await state.get_data()
    amt = parse_num(message.text)
    mode = data['mode']
    db_amt = amt if mode == 'add' else -amt
    
    conn = sqlite3.connect('debts_v2.db')
    c = conn.cursor()
    c.execute("UPDATE clients SET balance = balance + ? WHERE id = ?", (db_amt, data['c_id']))
    c.execute("INSERT INTO transactions (owner_id, client_id, amount, type, date) VALUES (?, ?, ?, ?, ?)",
              (message.from_user.id, data['c_id'], amt, mode, get_uzb_time().strftime("%Y-%m-%d")))
    c.execute("SELECT name, balance FROM clients WHERE id = ?", (data['c_id'],))
    name, bal = c.fetchone()
    conn.commit()
    conn.close()
    
    await message.answer(f"✅ Bajarildi!\n👤 {name}\n💰 Yangi balans: {format_num(bal)} so'm", 
                         reply_markup=main_menu(message.from_user.id))
    await state.clear()

@dp.message(F.text == "📊 Statistika")
async def my_stats(message: types.Message):
    conn = sqlite3.connect('debts_v2.db')
    c = conn.cursor()
    c.execute("SELECT SUM(balance) FROM clients WHERE owner_id=?", (message.from_user.id,))
    total = c.fetchone()[0] or 0
    conn.close()
    await message.answer(f"💰 Sizdagi jami haqdorlik:\n**{format_num(total)}** so'm", parse_mode="Markdown")

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
