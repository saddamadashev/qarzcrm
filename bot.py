import asyncio
import sqlite3
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

# --- SOZLAMALAR ---
TOKEN = "SIZNING_TOKENINGIZ"
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

# --- HOLATLAR (FSM) ---
class Form(StatesGroup):
    adding_client = State()
    adding_debt = State()
    subtracting_debt = State()

# --- KLAVIATURALAR ---
def main_menu():
    kb = [
        [KeyboardButton(text="👥 Mijozlar"), KeyboardButton(text="➕ Mijoz qo'shish")],
        [KeyboardButton(text="📊 Statistika (Oy/Yil)")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def client_inline_kb(client_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Qarz qo'shish", callback_data=f"add_{client_id}"),
         InlineKeyboardButton(text="➖ Qarz ayirish", callback_data=f"sub_{client_id}")],
        [InlineKeyboardButton(text="📜 Tarix", callback_data=f"history_{client_id}")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_list")]
    ])

# --- HANDLERLAR ---

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("Buxgalteriya botiga xush kelibsiz!", reply_markup=main_menu())

@dp.message(F.text == "➕ Mijoz qo'shish")
async def add_client_start(message: types.Message, state: FSMContext):
    await message.answer("Mijoz ismini kiriting:")
    await state.set_state(Form.adding_client)

@dp.message(Form.adding_client)
async def client_named(message: types.Message, state: FSMContext):
    name = message.text
    conn = sqlite3.connect('debts.db')
    c = conn.cursor()
    try:
        c.execute("INSERT INTO clients (name) VALUES (?)", (name,))
        conn.commit()
        await message.answer(f"✅ Mijoz '{name}' qo'shildi!", reply_markup=main_menu())
    except:
        await message.answer("❌ Bu ismli mijoz allaqachon mavjud.")
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
        await message.answer("Hozircha mijozlar yo'q.")
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{c[1]} ({c[2]:.1f} sum)", callback_data=f"view_{c[0]}")] for c in clients
    ])
    await message.answer("Mijozni tanlang:", reply_markup=kb)

@dp.callback_query(F.data.startswith("view_"))
async def view_client(callback: types.CallbackQuery):
    client_id = callback.data.split("_")[1]
    conn = sqlite3.connect('debts.db')
    c = conn.cursor()
    c.execute("SELECT name, balance FROM clients WHERE id=?", (client_id,))
    client = c.fetchone()
    conn.close()
    
    text = f"👤 **Mijoz:** {client[0]}\n💰 **Umumiy qarz:** {client[1]:.2f} so'm"
    await callback.message.edit_text(text, reply_markup=client_inline_kb(client_id), parse_mode="Markdown")

@dp.callback_query(F.data.startswith("add_") | F.data.startswith("sub_"))
async def adjust_debt(callback: types.CallbackQuery, state: FSMContext):
    action, client_id = callback.data.split("_")
    await state.update_data(client_id=client_id, action=action)
    await callback.message.answer(f"Summani kiriting (Faqat raqam):")
    await state.set_state(Form.adding_debt if action == "add" else Form.subtracting_debt)

@dp.message(Form.adding_debt)
@dp.message(Form.subtracting_debt)
async def process_debt(message: types.Message, state: FSMContext):
    data = await state.get_data()
    client_id = data['client_id']
    action = "add" if await state.get_state() == Form.adding_debt else "sub"
    
    try:
        amount = float(message.text)
        if action == "sub": amount = -amount
        
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        conn = sqlite3.connect('debts.db')
        c = conn.cursor()
        # Balansni yangilash
        c.execute("UPDATE clients SET balance = balance + ? WHERE id = ?", (amount, client_id))
        # Tarixga yozish
        c.execute("INSERT INTO transactions (client_id, amount, date) VALUES (?, ?, ?)", (client_id, amount, now))
        conn.commit()
        conn.close()
        
        await message.answer(f"✅ Muvaffaqiyatli bajarildi! (Sana: {now})", reply_markup=main_menu())
    except ValueError:
        await message.answer("Iltimos, faqat raqam kiriting.")
    
    await state.clear()

@dp.message(F.text == "📊 Statistika (Oy/Yil)")
async def show_stats(message: types.Message):
    conn = sqlite3.connect('debts.db')
    c = conn.cursor()
    
    # Umumiy qarz
    c.execute("SELECT SUM(balance) FROM clients")
    total = c.fetchone()[0] or 0
    
    # Joriy oy statistikasi
    this_month = datetime.now().strftime("%Y-%m")
    c.execute("SELECT SUM(amount) FROM transactions WHERE date LIKE ?", (f"{this_month}%",))
    monthly = c.fetchone()[0] or 0
    
    conn.close()
    
    text = (f"📈 **Statistika**\n\n"
            f"💵 **Jami qarzlar:** {total:.2f}\n"
            f"📅 **Shu oyda o'zgarish:** {monthly:.2f}")
    await message.answer(text, parse_mode="Markdown")

@dp.callback_query(F.data == "back_to_list")
async def back_to_list(callback: types.CallbackQuery):
    await list_clients(callback.message)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())