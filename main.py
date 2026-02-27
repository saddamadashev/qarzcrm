import asyncio
import sqlite3
import logging
import re
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

# Loglarni yoqish (xatolikni aniq ko'rish uchun)
logging.basicConfig(level=logging.INFO)

# --- SOZLAMALAR ---
# Tokenni BotFatherdan qaytadan aniq nusxalab qo'ying
TOKEN = "7968516598:AAHRE5zJ19D0_755S3y_6-uGjW5fT0E89_M"
ADMIN_ID = 565876427  # BU YERGA O'ZINGIZNING ID-INGIZNI YOZING

bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- YORDAMCHI FUNKSIYALAR ---
def get_uzb_time():
    return datetime.utcnow() + timedelta(hours=5)

def format_num(num):
    return f"{int(num or 0):,}".replace(",", " ")

def parse_num(text):
    clean_text = re.sub(r'[^\d]', '', text)
    return float(clean_text) if clean_text else 0

# --- BAZA ---
def init_db():
    conn = sqlite3.connect('baza.db')
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, name TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS clients (id INTEGER PRIMARY KEY AUTOINCREMENT, owner_id INTEGER, name TEXT, balance REAL DEFAULT 0)')
    conn.commit()
    conn.close()

init_db()

class Form(StatesGroup):
    adding_client = State()
    amount_input = State()

# --- MENU ---
def main_menu(user_id):
    kb = [
        [KeyboardButton(text="👥 Mijozlarim"), KeyboardButton(text="📊 Statistika")],
        [KeyboardButton(text="➕ Mijoz qo'shish"), KeyboardButton(text="📋 Hisobot")]
    ]
    if user_id == ADMIN_ID:
        kb.append([KeyboardButton(text="👑 Admin Panel")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

# --- HANDLERLAR ---
@dp.message(Command("start"))
async def start(message: types.Message):
    conn = sqlite3.connect('baza.db')
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users VALUES (?, ?)", (message.from_user.id, message.from_user.full_name))
    conn.commit()
    conn.close()
    await message.answer("✅ Tizim ishga tushdi.", reply_markup=main_menu(message.from_user.id))

@dp.message(F.text == "➕ Mijoz qo'shish")
async def add_cl(message: types.Message, state: FSMContext):
    await message.answer("👤 Ismini yozing:")
    await state.set_state(Form.adding_client)

@dp.message(Form.adding_client)
async def save_cl(message: types.Message, state: FSMContext):
    conn = sqlite3.connect('baza.db')
    c = conn.cursor()
    c.execute("INSERT INTO clients (owner_id, name) VALUES (?, ?)", (message.from_user.id, message.text))
    conn.commit()
    conn.close()
    await message.answer(f"✅ {message.text} qo'shildi.", reply_markup=main_menu(message.from_user.id))
    await state.clear()

@dp.message(F.text == "📋 Hisobot")
async def report(message: types.Message):
    conn = sqlite3.connect('baza.db')
    c = conn.cursor()
    c.execute("SELECT name, balance FROM clients WHERE owner_id=?", (message.from_user.id,))
    data = c.fetchall()
    conn.close()
    if not data: return await message.answer("Mijozlar yo'q.")
    
    txt = "📋 **HISOBOT**\n\n"
    total = 0
    for n, b in data:
        txt += f"👤 {n}: `{format_num(b)}` so'm\n"
        total += b
    txt += f"\n💰 **Jami:** `{format_num(total)}` so'm"
    await message.answer(txt, parse_mode="Markdown")

@dp.message(F.text == "👑 Admin Panel")
async def admin(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    conn = sqlite3.connect('baza.db')
    c = conn.cursor()
    c.execute("SELECT u.name, SUM(c.balance) FROM users u LEFT JOIN clients c ON u.user_id = c.owner_id GROUP BY u.user_id")
    stats = c.fetchall()
    conn.close()
    txt = "👑 **ADMIN PANEL**\n\n"
    for n, t in stats:
        txt += f"👤 {n or 'Noma`lum'}: `{format_num(t)}` so'm\n"
    await message.answer(txt, parse_mode="Markdown")

@dp.message(F.text == "👥 Mijozlarim")
async def list_cl(message: types.Message):
    conn = sqlite3.connect('baza.db')
    c = conn.cursor()
    c.execute("SELECT id, name, balance FROM clients WHERE owner_id=?", (message.from_user.id,))
    clients = c.fetchall()
    conn.close()
    if not clients: return await message.answer("Ro'yxat bo'sh.")
    btns = [[InlineKeyboardButton(text=f"{cl[1]} | {format_num(cl[2])}", callback_data=f"v_{cl[0]}")] for cl in clients]
    await message.answer("Mijozni tanlang:", reply_markup=InlineKeyboardMarkup(inline_keyboard=btns))

@dp.callback_query(F.data.startswith("v_"))
async def view(call: types.CallbackQuery):
    c_id = call.data.split("_")[1]
    conn = sqlite3.connect('baza.db')
    c = conn.cursor()
    c.execute("SELECT name, balance FROM clients WHERE id=?", (c_id,))
    cl = c.fetchone()
    conn.close()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Qarz", callback_data=f"a_add_{c_id}"),
         InlineKeyboardButton(text="✅ To'lov", callback_data=f"a_sub_{c_id}")]
    ])
    await call.message.edit_text(f"👤 {cl[0]}\n💰 `{format_num(cl[1])}` so'm", reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data.startswith("a_"))
async def act(call: types.CallbackQuery, state: FSMContext):
    _, mode, c_id = call.data.split("_")
    await state.update_data(c_id=c_id, mode=mode)
    await call.message.answer("Summani yozing (masalan: 500 000):")
    await state.set_state(Form.amount_input)

@dp.message(Form.amount_input)
async def process(message: types.Message, state: FSMContext):
    data = await state.get_data()
    amt = parse_num(message.text)
    db_amt = amt if data['mode'] == 'add' else -amt
    conn = sqlite3.connect('baza.db')
    c = conn.cursor()
    c.execute("UPDATE clients SET balance = balance + ? WHERE id = ?", (db_amt, data['c_id']))
    c.execute("SELECT name, balance FROM clients WHERE id = ?", (data['c_id'],))
    n, b = c.fetchone()
    conn.commit()
    conn.close()
    await message.answer(f"✅ {n}\n💰 Qoldiq: `{format_num(b)}` so'm", reply_markup=main_menu(message.from_user.id), parse_mode="Markdown")
    await state.clear()

@dp.message(F.text == "📊 Statistika")
async def my_stats(message: types.Message):
    conn = sqlite3.connect('baza.db')
    c = conn.cursor()
    c.execute("SELECT SUM(balance) FROM clients WHERE owner_id=?", (message.from_user.id,))
    total = c.fetchone()[0] or 0
    conn.close()
    await message.answer(f"💰 Jami haqdorlik: **{format_num(total)}** so'm", parse_mode="Markdown")

async def main():
    try:
        await asyncio.sleep(2) # Railway uchun delay
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    except Exception as e:
        logging.error(f"Telegram server xatosi: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
