import asyncio
import sqlite3
import os
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

# --- SOZLAMALAR ---
# Railway Variables bo'limiga BOT_TOKEN qo'shishni unutmang!
TOKEN = os.getenv("BOT_TOKEN", "7968516598:AAHRE5zJ19D0_755S3y_6-uGjW5fT0E89_M") # O'zingiznikini ham qo'yishingiz mumkin

bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- BAZA BILAN ISHLASH ---
def init_db():
    conn = sqlite3.connect('debts.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS clients 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, balance REAL DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS transactions 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, client_id INTEGER, amount REAL, date TEXT)''')
    conn.commit()
    conn.close()

init_db()

# --- HOLATLAR ---
class Form(StatesGroup):
    adding_client = State()
    amount_input = State()

# --- KLAVIATURALAR ---
def main_menu():
    kb = [
        [KeyboardButton(text="👥 Mijozlar"), KeyboardButton(text="➕ Mijoz qo'shish")],
        [KeyboardButton(text="📊 Statistika")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

# --- HANDLERLAR ---

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("💰 Buxgalteriya botiga xush kelibsiz!", reply_markup=main_menu())

@dp.message(F.text == "➕ Mijoz qo'shish")
async def add_client_start(message: types.Message, state: FSMContext):
    await message.answer("👤 Yangi mijoz ismini kiriting:")
    await state.set_state(Form.adding_client)

@dp.message(Form.adding_client)
async def client_named(message: types.Message, state: FSMContext):
    name = message.text
    conn = sqlite3.connect('debts.db')
    c = conn.cursor()
    try:
        c.execute("INSERT INTO clients (name) VALUES (?)", (name,))
        conn.commit()
        await message.answer(f"✅ {name} muvaffaqiyatli qo'shildi!", reply_markup=main_menu())
    except:
        await message.answer("❌ Bu ismli mijoz bazada bor.")
    conn.close()
    await state.clear()

@dp.message(F.text == "👥 Mijozlar")
async def list_clients(message: types.Message):
    conn = sqlite3.connect('debts.db')
    c = conn.cursor()
    c.execute("SELECT id, name, balance FROM clients")
    clients = c.fetchall()
    conn.close()

    if not clients:
        await message.answer("📭 Mijozlar ro'yxati bo'sh.")
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for c in clients:
        kb.inline_keyboard.append([InlineKeyboardButton(text=f"{c[1]} | {c[2]:.1f}", callback_data=f"view_{c[0]}")])
    
    await message.answer("👇 Mijozni tanlang:", reply_markup=kb)

@dp.callback_query(F.data.startswith("view_"))
async def view_client(callback: types.CallbackQuery):
    client_id = callback.data.split("_")[1]
    conn = sqlite3.connect('debts.db')
    c = conn.cursor()
    c.execute("SELECT name, balance FROM clients WHERE id=?", (client_id,))
    client = c.fetchone()
    conn.close()
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Qarz qo'shish", callback_data=f"act_add_{client_id}"),
         InlineKeyboardButton(text="➖ Qarz ayirish", callback_data=f"act_sub_{client_id}")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_list")]
    ])
    
    text = f"👤 **Mijoz:** {client[0]}\n💰 **Joriy hisob:** {client[1]:.2f} so'm"
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data.startswith("act_"))
async def action_debt(callback: types.CallbackQuery, state: FSMContext):
    _, mode, client_id = callback.data.split("_")
    await state.update_data(c_id=client_id, mode=mode)
    await callback.message.answer(f"💵 Summani kiriting ({'qo`shish' if mode=='add' else 'ayirish'}):")
    await state.set_state(Form.amount_input)

@dp.message(Form.amount_input)
async def process_amount(message: types.Message, state: FSMContext):
    data = await state.get_data()
    try:
        amount = float(message.text)
        if data['mode'] == 'sub': amount = -amount
        
        conn = sqlite3.connect('debts.db')
        c = conn.cursor()
        now = datetime.now().strftime("%d.%m.%Y %H:%M")
        
        c.execute("UPDATE clients SET balance = balance + ? WHERE id = ?", (amount, data['c_id']))
        c.execute("INSERT INTO transactions (client_id, amount, date) VALUES (?, ?, ?)", (data['c_id'], amount, now))
        conn.commit()
        conn.close()
        
        await message.answer(f"✅ Amaliyot bajarildi!\nVaqt: {now}", reply_markup=main_menu())
    except:
        await message.answer("❌ Faqat son kiriting!")
    await state.clear()

@dp.message(F.text == "📊 Statistika")
async def stats(message: types.Message):
    conn = sqlite3.connect('debts.db')
    c = conn.cursor()
    c.execute("SELECT SUM(balance) FROM clients")
    total = c.fetchone()[0] or 0
    
    this_month = datetime.now().strftime(".%m.%Y")
    c.execute("SELECT SUM(amount) FROM transactions WHERE date LIKE ?", (f"%{this_month}%",))
    monthly = c.fetchone()[0] or 0
    conn.close()
    
    await message.answer(f"📈 **Umumiy statistika:**\n\n💵 Jami qarzlar: {total:.2f}\n📅 Shu oydagi o'zgarish: {monthly:.2f}", parse_mode="Markdown")

@dp.callback_query(F.data == "back_to_list")
async def back(callback: types.CallbackQuery):
    await list_clients(callback.message)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())