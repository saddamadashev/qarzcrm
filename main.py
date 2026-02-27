import asyncio
import sqlite3
import os
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

# --- SOZLAMALAR ---
TOKEN = os.getenv("BOT_TOKEN", "7968516598:AAHRE5zJ19D0_755S3y_6-uGjW5fT0E89_M")
ADMIN_ID = 12345678  # @userinfobot orqali olingan ID-ni yozing

bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- YORDAMCHI FUNKSIYALAR ---
def format_num(num):
    """Sonlarni 1 000 000 ko'rinishida formatlaydi"""
    return "{:,.0f}".format(num).replace(",", " ")

def parse_num(text):
    """Probel bilan yozilgan sonni raqamga o'tkazadi"""
    return float(text.replace(" ", "").replace(",", ""))

# --- BAZA BILAN ISHLASH ---
def init_db():
    conn = sqlite3.connect('debts.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)''')
    c.execute('''CREATE TABLE IF NOT EXISTS clients 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, owner_id INTEGER, name TEXT, balance REAL DEFAULT 0, last_update TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS transactions 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, client_id INTEGER, amount REAL, type TEXT, date TEXT)''')
    conn.commit()
    conn.close()

init_db()

class Form(StatesGroup):
    adding_client = State()
    amount_input = State()
    searching = State()
    broadcast = State()

# --- KLAVIATURALAR ---
def main_menu(user_id):
    kb = [
        [KeyboardButton(text="👥 Mijozlarim"), KeyboardButton(text="🔍 Qidirish")],
        [KeyboardButton(text="➕ Mijoz qo'shish"), KeyboardButton(text="📊 Statistika")],
        [KeyboardButton(text="⚠️ Muddat o'tganlar")]
    ]
    if user_id == ADMIN_ID:
        kb.append([KeyboardButton(text="👑 Admin Panel"), KeyboardButton(text="📢 Xabar yuborish")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

# --- HANDLERLAR ---

@dp.message(Command("start"))
async def start(message: types.Message):
    conn = sqlite3.connect('debts.db')
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (message.from_user.id,))
    conn.commit()
    conn.close()
    await message.answer("🚀 Buxgalteriya tizimiga xush kelibsiz!", reply_markup=main_menu(message.from_user.id))

@dp.message(F.text == "➕ Mijoz qo'shish")
async def add_client_start(message: types.Message, state: FSMContext):
    await message.answer("👤 Mijoz ismini kiriting:")
    await state.set_state(Form.adding_client)

@dp.message(Form.adding_client)
async def client_named(message: types.Message, state: FSMContext):
    now = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect('debts.db')
    c = conn.cursor()
    c.execute("INSERT INTO clients (owner_id, name, last_update) VALUES (?, ?, ?)", (message.from_user.id, message.text, now))
    conn.commit()
    conn.close()
    await message.answer(f"✅ {message.text} qo'shildi!", reply_markup=main_menu(message.from_user.id))
    await state.clear()

@dp.message(F.text == "👥 Mijozlarim")
async def list_clients(message: types.Message):
    conn = sqlite3.connect('debts.db')
    c = conn.cursor()
    c.execute("SELECT id, name, balance FROM clients WHERE owner_id=?", (message.from_user.id,))
    clients = c.fetchall()
    conn.close()
    if not clients:
        await message.answer("Hozircha mijozlar yo'q.")
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"{cl[1]} | {format_num(cl[2])}", callback_data=f"view_{cl[0]}")] for cl in clients])
    await message.answer("📋 Mijozlaringiz:", reply_markup=kb)

@dp.callback_query(F.data.startswith("view_"))
async def view(callback: types.CallbackQuery):
    c_id = callback.data.split("_")[1]
    conn = sqlite3.connect('debts.db')
    c = conn.cursor()
    c.execute("SELECT name, balance FROM clients WHERE id=?", (c_id,))
    cl = c.fetchone()
    conn.close()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Sotuv", callback_data=f"act_add_{c_id}"), InlineKeyboardButton(text="✅ To'lov", callback_data=f"act_sub_{c_id}")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_list")]
    ])
    await callback.message.edit_text(f"👤 {cl[0]}\n💰 Qarzi: {format_num(cl[1])} so'm", reply_markup=kb)

@dp.callback_query(F.data.startswith("act_"))
async def act(callback: types.CallbackQuery, state: FSMContext):
    _, mode, c_id = callback.data.split("_")
    await state.update_data(c_id=c_id, mode=mode)
    await callback.message.answer("💳 Summani kiriting (masalan: 1 500 000):")
    await state.set_state(Form.amount_input)

@dp.message(Form.amount_input)
async def process_amount(message: types.Message, state: FSMContext):
    data = await state.get_data()
    try:
        # Probellarni olib tashlab hisoblash
        amt = parse_num(message.text)
        if data['mode'] == 'sub': amt = -amt
        
        now_dt = datetime.now().strftime("%Y-%m-%d %H:%M")
        now_date = datetime.now().strftime("%Y-%m-%d")
        
        conn = sqlite3.connect('debts.db')
        c = conn.cursor()
        c.execute("UPDATE clients SET balance = balance + ?, last_update = ? WHERE id = ?", (amt, now_date, data['c_id']))
        c.execute("INSERT INTO transactions (client_id, amount, type, date) VALUES (?, ?, ?, ?)", (data['c_id'], amt, data['mode'], now_dt))
        conn.commit()
        conn.close()
        
        await message.answer(f"✅ Bajarildi!\nSumma: {format_num(abs(amt))} so'm", reply_markup=main_menu(message.from_user.id))
    except ValueError:
        await message.answer("❌ Xato! Faqat raqam kiriting (masalan: 5 000 000).")
    await state.clear()

@dp.message(F.text == "📊 Statistika")
async def statistics(message: types.Message):
    conn = sqlite3.connect('debts.db')
    c = conn.cursor()
    # Shaxsiy jami qarz
    c.execute("SELECT SUM(balance) FROM clients WHERE owner_id=?", (message.from_user.id,))
    total = c.fetchone()[0] or 0
    
    # Shu oydagi savdo (faqat qo'shilgan summalar)
    this_month = datetime.now().strftime("%Y-%m")
    c.execute("""SELECT SUM(amount) FROM transactions 
                 JOIN clients ON transactions.client_id = clients.id 
                 WHERE clients.owner_id=? AND amount > 0 AND date LIKE ?""", (message.from_user.id, f"{this_month}%"))
    monthly_sales = c.fetchone()[0] or 0
    
    conn.close()
    await message.answer(f"📊 **Sizning statistikangiz:**\n\n💰 Umumiy qarzlar: {format_num(total)} so'm\n📈 Shu oydagi jami sotuv: {format_num(monthly_sales)} so'm", parse_mode="Markdown")

@dp.message(F.text == "⚠️ Muddat o'tganlar")
async def expired_debts(message: types.Message):
    limit = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    conn = sqlite3.connect('debts.db')
    c = conn.cursor()
    c.execute("SELECT name, balance, last_update FROM clients WHERE owner_id=? AND balance > 0 AND last_update < ?", (message.from_user.id, limit))
    res = c.fetchall()
    conn.close()
    if not res:
        await message.answer("Tinchlik! Muddat o'tgan qarzlar yo'q.")
    else:
        text = "⚠️ **30 kundan beri to'lanmagan:**\n\n"
        for r in res:
            text += f"👤 {r[0]} | 💰 {format_num(r[1])} so'm\n"
        await message.answer(text, parse_mode="Markdown")

@dp.message(F.text == "👑 Admin Panel")
async def admin_panel(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    conn = sqlite3.connect('debts.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    u_count = c.fetchone()[0]
    c.execute("SELECT SUM(balance) FROM clients")
    total = c.fetchone()[0] or 0
    conn.close()
    await message.answer(f"👑 **ADMIN PANEL**\n\n👥 Bot a'zolari: {u_count}\n💸 Tizimdagi jami pul: {format_num(total)} so'm")

@dp.callback_query(F.data == "back_to_list")
async def back(callback: types.CallbackQuery):
    await list_clients(callback.message)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())