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
TOKEN = os.getenv("BOT_TOKEN", "7968516598:AAHRE5zJ19D0_755S3y_6-uGjW5fT0E89_M")
bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- YORDAMCHI FUNKSIYALAR (IDEAL FORMATLASH) ---
def get_uzb_time():
    return datetime.utcnow() + timedelta(hours=5)

def format_num(num):
    """Raqamni 1 000 000.00 ko'rinishidan 1 000 000 ko'rinishiga o'tkazadi"""
    try:
        # f-string orqali mingliklarni ajratamiz (1,000,000) keyin vergulni bo'sh joyga almashtiramiz
        return f"{int(num):,}".replace(",", " ")
    except:
        return "0"

def parse_num(text):
    """Matndan faqat sonlarni sug'urib oladi (nuqta, vergul, bo'sh joy va $ ni tozalaydi)"""
    # Faqat raqamlarni qoldirish (masalan: "1 200 000 $" -> "1200000")
    clean_text = re.sub(r'[^\d]', '', text)
    return float(clean_text) if clean_text else 0

# --- BAZA ---
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

# --- MENU ---
def main_menu():
    kb = [
        [KeyboardButton(text="👥 Mijozlarim"), KeyboardButton(text="📊 Statistika")],
        [KeyboardButton(text="➕ Mijoz qo'shish")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

# --- HANDLERLAR ---
@dp.message(Command("start"))
async def start(message: types.Message):
    conn = sqlite3.connect('debts.db')
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (message.from_user.id,))
    conn.commit()
    conn.close()
    await message.answer("💰 **Qarz daftari botiga xush kelibsiz!**", reply_markup=main_menu(), parse_mode="Markdown")

@dp.message(F.text == "➕ Mijoz qo'shish")
async def add_client(message: types.Message, state: FSMContext):
    await message.answer("👤 **Mijoz ismini kiriting:**", parse_mode="Markdown")
    await state.set_state(Form.adding_client)

@dp.message(Form.adding_client)
async def save_client(message: types.Message, state: FSMContext):
    now = get_uzb_time().strftime("%Y-%m-%d")
    conn = sqlite3.connect('debts.db')
    c = conn.cursor()
    c.execute("INSERT INTO clients (owner_id, name, last_update) VALUES (?, ?, ?)", (message.from_user.id, message.text, now))
    conn.commit()
    conn.close()
    await message.answer(f"✅ **{message.text}** ro'yxatga qo'shildi!", reply_markup=main_menu(), parse_mode="Markdown")
    await state.clear()

@dp.message(F.text == "👥 Mijozlarim")
async def list_clients(message: types.Message):
    conn = sqlite3.connect('debts.db')
    c = conn.cursor()
    c.execute("SELECT id, name, balance FROM clients WHERE owner_id=?", (message.from_user.id,))
    clients = c.fetchall()
    conn.close()
    
    if not clients:
        await message.answer("📭 Hozircha mijozlar yo'q.")
        return
    
    buttons = [[InlineKeyboardButton(text=f"👤 {cl[1]} | {format_num(cl[2])} so'm", callback_data=f"view_{cl[0]}")] for cl in clients]
    await message.answer("📋 **Mijozlaringiz va qarzlar:**", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@dp.callback_query(F.data.startswith("view_"))
async def view_client(callback: types.CallbackQuery):
    c_id = callback.data.split("_")[1]
    conn = sqlite3.connect('debts.db')
    c = conn.cursor()
    c.execute("SELECT name, balance FROM clients WHERE id=?", (c_id,))
    cl = c.fetchone()
    conn.close()
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Qarz qo'shish", callback_data=f"act_add_{c_id}"),
         InlineKeyboardButton(text="✅ To'lov olish", callback_data=f"act_sub_{c_id}")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_list")]
    ])
    await callback.message.edit_text(
        f"👤 Mijoz: **{cl[0]}**\n💰 Hozirgi qarz: `{format_num(cl[1])}` so'm", 
        reply_markup=kb, parse_mode="Markdown"
    )

@dp.callback_query(F.data == "back_list")
async def back_list(callback: types.CallbackQuery):
    # Ro'yxatni yangilash kodi
    conn = sqlite3.connect('debts.db')
    c = conn.cursor()
    c.execute("SELECT id, name, balance FROM clients WHERE owner_id=?", (callback.from_user.id,))
    clients = c.fetchall()
    buttons = [[InlineKeyboardButton(text=f"{cl[1]} | {format_num(cl[2])} so'm", callback_data=f"view_{cl[0]}")] for cl in clients]
    await callback.message.edit_text("📋 **Mijozlar ro'yxati:**", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

@dp.callback_query(F.data.startswith("act_"))
async def action(callback: types.CallbackQuery, state: FSMContext):
    _, mode, c_id = callback.data.split("_")
    await state.update_data(c_id=c_id, mode=mode)
    txt = "➕ **Summani kiriting (Qarz qo'shish):**" if mode == 'add' else "✅ **To'lov summasini kiriting:**"
    await callback.message.answer(txt, parse_mode="Markdown")
    await state.set_state(Form.amount_input)

@dp.message(Form.amount_input)
async def process_amount(message: types.Message, state: FSMContext):
    data = await state.get_data()
    amt = parse_num(message.text)
    
    if amt <= 0:
        await message.answer("⚠️ Iltimos, faqat musbat son kiriting!")
        return

    mode = data['mode']
    db_amt = amt if mode == 'add' else -amt
    
    conn = sqlite3.connect('debts.db')
    c = conn.cursor()
    c.execute("UPDATE clients SET balance = balance + ?, last_update = ? WHERE id = ?", 
              (db_amt, get_uzb_time().strftime("%Y-%m-%d"), data['c_id']))
    c.execute("SELECT name, balance FROM clients WHERE id = ?", (data['c_id'],))
    client_name, new_balance = c.fetchone()
    conn.commit()
    conn.close()
    
    # --- IDEAL CHEK FORMATI ---
    type_str = "➕ Qarz yozildi" if mode == 'add' else "✅ To'lov qilindi"
    color_emoji = "🔴" if mode == 'add' else "🟢"
    
    response = (
        f"📝 **AMALIYOT TASDIQLANDI**\n"
        f"━━━━━━━━━━━━━━━\n"
        f"👤 **Mijoz:** {client_name}\n"
        f"💰 **Summa:** {format_num(amt)} so'm\n"
        f"🔄 **Turi:** {type_str}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"{color_emoji} **Yangi balans:** `{format_num(new_balance)}` so'm\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📅 {get_uzb_time().strftime('%d.%m.%Y | %H:%M')}"
    )
    
    await message.answer(response, reply_markup=main_menu(), parse_mode="Markdown")
    await state.clear()

@dp.message(F.text == "📊 Statistika")
async def stats(message: types.Message):
    conn = sqlite3.connect('debts.db')
    c = conn.cursor()
    c.execute("SELECT SUM(balance) FROM clients WHERE owner_id=?", (message.from_user.id,))
    total = c.fetchone()[0] or 0
    conn.close()
    await message.answer(f"📊 **Umumiy kutilayotgan haq:**\n\n💰 `{format_num(total)}` so'm", parse_mode="Markdown")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
