import logging
import sqlite3
import asyncio
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

# --- KONFIGURATSIYA ---
TOKEN = "8759158410:AAFjHdOY5R95WlC0GG4n5dG7koRTPvv68jE"
ADMIN_ID = 565876427  # O'zingizning Telegram ID raqamingizni yozing

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- FSM HOLATLARI ---
class DebtStates(StatesGroup):
    waiting_for_client_name = State()
    waiting_for_amount_add = State()
    waiting_for_amount_sub = State()

# --- MA'LUMOTLAR BAZASI ---
def db_query(query, params=(), fetch=False):
    conn = sqlite3.connect('qarz_daftari.db')
    cursor = conn.cursor()
    cursor.execute(query, params)
    res = cursor.fetchall() if fetch else None
    conn.commit()
    conn.close()
    return res

def init_db():
    db_query('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)''')
    db_query('''CREATE TABLE IF NOT EXISTS clients (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                owner_id INTEGER, 
                name TEXT, 
                total_debt REAL DEFAULT 0)''')
    db_query('''CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                client_id INTEGER, 
                amount REAL, 
                type TEXT, 
                date TEXT)''')

init_db()

# --- TUGMALAR ---
def get_main_kb(user_id):
    kb = [
        [KeyboardButton(text="👤 Mijozlarim"), KeyboardButton(text="➕ Mijoz qo'shish")],
        [KeyboardButton(text="📊 Umumiy hisobot")]
    ]
    if user_id == ADMIN_ID:
        kb.append([KeyboardButton(text="⚙️ Admin Paneli")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

# --- ASOSIY KOMANDALAR ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    db_query("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (message.from_id,))
    await message.answer(f"Salom {message.from_user.first_name}! Bu sizning shaxsiy qarz daftaringiz.", 
                         reply_markup=get_main_kb(message.from_id))

# --- MIJOZ QO'SHISH ---
@dp.message(F.text == "➕ Mijoz qo'shish")
async def add_client(message: types.Message, state: FSMContext):
    await message.answer("Yangi mijoz ismini kiriting:", reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(DebtStates.waiting_for_client_name)

@dp.message(DebtStates.waiting_for_client_name)
async def process_client_name(message: types.Message, state: FSMContext):
    db_query("INSERT INTO clients (owner_id, name) VALUES (?, ?)", (message.from_id, message.text))
    await state.clear()
    await message.answer(f"✅ {message.text} muvaffaqiyatli qo'shildi!", reply_markup=get_main_kb(message.from_id))

# --- MIJOZLAR RO'YXATI ---
@dp.message(F.text == "👤 Mijozlarim")
async def list_clients(message: types.Message):
    clients = db_query("SELECT id, name, total_debt FROM clients WHERE owner_id = ?", (message.from_id,), True)
    if not clients:
        return await message.answer("Hali mijozlar yo'q.")
    
    builder = InlineKeyboardBuilder()
    for c_id, name, debt in clients:
        builder.row(InlineKeyboardButton(text=f"{name} | {debt} so'm", callback_data=f"view_{c_id}"))
    await message.answer("Mijozni tanlang:", reply_markup=builder.as_markup())

# --- MIJOZ USTIDA AMALLAR ---
@dp.callback_query(F.data.startswith("view_"))
async def view_client(callback: types.CallbackQuery, state: FSMContext):
    client_id = callback.data.split("_")[1]
    client = db_query("SELECT name, total_debt FROM clients WHERE id = ?", (client_id,), True)[0]
    
    await state.update_data(c_id=client_id, c_name=client[0])
    
    text = f"👤 **Mijoz:** {client[0]}\n💰 **Jami qarz:** {client[1]} so'm"
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="➕ Qarz qo'shish", callback_data=f"add_{client_id}"),
                InlineKeyboardButton(text="➖ Qarz ayirish", callback_data=f"sub_{client_id}"))
    builder.row(InlineKeyboardButton(text="📜 Tarix", callback_data=f"hist_{client_id}"),
                InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"del_{client_id}"))
    builder.row(InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back_to_list"))
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")

# --- QARZ QO'SHISH/AYIRISH ---
@dp.callback_query(F.data.startswith(("add_", "sub_")))
async def change_debt(callback: types.CallbackQuery, state: FSMContext):
    action, c_id = callback.data.split("_")
    await state.update_data(c_id=c_id, action=action)
    await callback.message.answer(f"Summani kiriting (Faqat raqam):")
    await state.set_state(DebtStates.waiting_for_amount_add if action == "add" else DebtStates.waiting_for_amount_sub)

@dp.message(DebtStates.waiting_for_amount_add)
@dp.message(DebtStates.waiting_for_amount_sub)
async def process_amount(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text)
    except ValueError:
        return await message.answer("⚠️ Iltimos, faqat raqam kiriting:")
    
    data = await state.get_data()
    c_id, action = data['c_id'], data['action']
    now = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    
    status_text = "Qo'shildi" if action == "add" else "To'landi"
    sign = "➕" if action == "add" else "➖"
    
    if action == "add":
        db_query("UPDATE clients SET total_debt = total_debt + ? WHERE id = ?", (amount, c_id))
    else:
        db_query("UPDATE clients SET total_debt = total_debt - ? WHERE id = ?", (amount, c_id))
    
    db_query("INSERT INTO history (client_id, amount, type, date) VALUES (?, ?, ?, ?)", (c_id, amount, sign, now))
    res = db_query("SELECT name, total_debt FROM clients WHERE id = ?", (c_id,), True)[0]
    
    receipt = (f"🧾 **AMALAYOT TASDIQLANDI**\n"
               f"━━━━━━━━━━━━━━\n"
               f"👤 Mijoz: {res[0]}\n"
               f"💰 Miqdor: {amount} so'm\n"
               f"📝 Holat: {status_text}\n"
               f"📅 Sana: {now}\n"
               f"━━━━━━━━━━━━━━\n"
               f"💳 Jami qarz: {res[1]} so'm")
    
    await state.clear()
    await message.answer(receipt, reply_markup=get_main_kb(message.from_id), parse_mode="Markdown")

# --- O'CHIRISH VA ORQAGA ---
@dp.callback_query(F.data.startswith("del_"))
async def delete_client(callback: types.CallbackQuery):
    c_id = callback.data.split("_")[1]
    db_query("DELETE FROM clients WHERE id = ?", (c_id,))
    db_query("DELETE FROM history WHERE client_id = ?", (c_id,))
    await callback.answer("Mijoz o'chirildi")
    await list_clients(callback.message)

@dp.callback_query(F.data == "back_to_list")
async def back_to_list(callback: types.CallbackQuery):
    await list_clients(callback.message)

# --- ADMIN PANEL ---
@dp.message(F.text == "⚙️ Admin Paneli")
async def admin_main(message: types.Message):
    if message.from_id != ADMIN_ID: return
    users_count = db_query("SELECT COUNT(*) FROM users", fetch=True)[0][0]
    total_debts = db_query("SELECT SUM(total_debt) FROM clients", fetch=True)[0][0] or 0
    await message.answer(f"👑 **ADMIN PANEL**\n\n👥 Umumiy foydalanuvchilar: {users_count}\n💸 Tizimdagi jami qarzlar: {total_debts} so'm", parse_mode="Markdown")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
