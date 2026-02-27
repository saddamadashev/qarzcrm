import asyncio
import sqlite3
import logging
import re
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import (
    InlineKeyboardMarkup, 
    InlineKeyboardButton, 
    ReplyKeyboardMarkup, 
    KeyboardButton,
    CallbackQuery
)

# 1. LOGGING (Xatoliklarni kuzatish uchun)
logging.basicConfig(level=logging.INFO)

# 2. SOZLAMALAR (Siz bergan ma'lumotlar)
TOKEN = "8759158410:AAFH4Lz-1VsndTC4VRABU7uHYU-qCFoY60Q"
ADMIN_ID = 565876427

bot = Bot(token=TOKEN)
dp = Dispatcher()
DB_PATH = 'baza.db'

# 3. YORDAMCHI FUNKSIYALAR
def format_num(num):
    """Raqamlarni chiroyli formatda chiqarish (masalan: 100 000)"""
    return f"{int(num or 0):,}".replace(",", " ")

def parse_num(text):
    """Matndan faqat raqamlarni ajratib olish"""
    clean_text = re.sub(r'[^\d]', '', text)
    return float(clean_text) if clean_text else 0

# 4. MA'LUMOTLAR BAZASI BILAN ISHLASH
def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, name TEXT)')
        c.execute('''CREATE TABLE IF NOT EXISTS clients 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, owner_id INTEGER, name TEXT, balance REAL DEFAULT 0)''')
        conn.commit()

# 5. HOLATLAR (FSM)
class Form(StatesGroup):
    adding_client = State()
    amount_input = State()

# 6. KLAVIATURALAR
def main_menu(user_id):
    kb = [
        [KeyboardButton(text="👥 Mijozlarim"), KeyboardButton(text="📊 Statistika")],
        [KeyboardButton(text="➕ Mijoz qo'shish"), KeyboardButton(text="📋 Hisobot")]
    ]
    if user_id == ADMIN_ID:
        kb.append([KeyboardButton(text="👑 Admin Panel")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

# 7. HANDLERLAR (BOT BUYRUQLARI)

@dp.message(Command("start"))
async def start(message: types.Message, state: FSMContext):
    await state.clear()
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO users VALUES (?, ?)", (message.from_user.id, message.from_user.full_name))
        conn.commit()
    
    await message.answer(
        f"✅ Assalomu alaykum, {message.from_user.first_name}!\nQarz daftariga xush kelibsiz.", 
        reply_markup=main_menu(message.from_user.id)
    )

@dp.message(F.text == "➕ Mijoz qo'shish")
async def add_cl(message: types.Message, state: FSMContext):
    await message.answer("👤 Mijoz ismini (yoki do'kon nomini) kiriting:")
    await state.set_state(Form.adding_client)

@dp.message(Form.adding_client)
async def save_cl(message: types.Message, state: FSMContext):
    if not message.text:
        return await message.answer("Iltimos, ism kiriting:")
        
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("INSERT INTO clients (owner_id, name) VALUES (?, ?)", (message.from_user.id, message.text))
        conn.commit()
    
    await message.answer(f"✅ Mijoz '{message.text}' muvaffaqiyatli qo'shildi.")
    await state.clear()

@dp.message(F.text == "👥 Mijozlarim")
async def list_cl(message: types.Message):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT id, name, balance FROM clients WHERE owner_id=?", (message.from_user.id,))
        clients = c.fetchall()
    
    if not clients:
        return await message.answer("📭 Hozircha mijozlar yo'q. Avval mijoz qo'shing.")
    
    btns = []
    for cl in clients:
        btns.append([InlineKeyboardButton(text=f"{cl[1]} | {format_num(cl[2])} so'm", callback_data=f"v_{cl[0]}")])
    
    await message.answer("👥 Mijozni tanlang:", reply_markup=InlineKeyboardMarkup(inline_keyboard=btns))

@dp.callback_query(F.data.startswith("v_"))
async def view_client(call: CallbackQuery):
    c_id = call.data.split("_")[1]
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT name, balance FROM clients WHERE id=?", (c_id,))
        cl = c.fetchone()
    
    if not cl:
        return await call.answer("Mijoz topilmadi.")

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="➕ Qarz yozish", callback_data=f"act_add_{c_id}"),
            InlineKeyboardButton(text="✅ To'lov olish", callback_data=f"act_sub_{c_id}")
        ]
    ])
    await call.message.edit_text(
        f"👤 Mijoz: {cl[0]}\n💰 Balans: {format_num(cl[1])} so'm", 
        reply_markup=kb
    )
    await call.answer()

@dp.callback_query(F.data.startswith("act_"))
async def action_input(call: CallbackQuery, state: FSMContext):
    _, mode, c_id = call.data.split("_")
    await state.update_data(c_id=c_id, mode=mode)
    
    txt = "➕ Qarz miqdorini kiriting:" if mode == 'add' else "✅ To'lov miqdorini kiriting:"
    await call.message.answer(txt)
    await state.set_state(Form.amount_input)
    await call.answer()

@dp.message(Form.amount_input)
async def process_amount(message: types.Message, state: FSMContext):
    amt = parse_num(message.text)
    if amt <= 0:
        return await message.answer("⚠️ Iltimos, faqat raqamlardan foydalanib summa kiriting:")

    data = await state.get_data()
    db_amt = amt if data['mode'] == 'add' else -amt
    
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("UPDATE clients SET balance = balance + ? WHERE id = ?", (db_amt, data['c_id']))
        c.execute("SELECT name, balance FROM clients WHERE id = ?", (data['c_id'],))
        res = c.fetchone()
        conn.commit()

    if res:
        await message.answer(
            f"✅ Amaliyot saqlandi!\n👤 {res[0]}\n💰 Yangi balans: {format_num(res[1])} so'm",
            reply_markup=main_menu(message.from_user.id)
        )
    await state.clear()

# 8. ASOSIY FUNKSIYA
async def main():
    init_db()
    # Eski xabarlarni o'chirib yuborish
    await bot.delete_webhook(drop_pending_updates=True)
    print("--- Bot muvaffaqiyatli ishga tushdi! ---")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot to'xtatildi")
