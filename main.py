Import asyncio
import sqlite3
import os
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

# --- SOZLAMALAR ---
TOKEN = os.getenv("BOT_TOKEN", "8759158410:AAFH4Lz-1VsndTC4VRABU7uHYU-qCFoY60Q")
ADMIN_ID = 565876427  # O'zingizning ID-ingizni yozing

bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- YORDAMCHI FUNKSIYALAR ---
def get_uzb_time():
    return datetime.utcnow() + timedelta(hours=5)

def format_num(num):
    return "{:,.0f}".format(num).replace(",", " ")

def parse_num(text):
    # Faqat raqamlarni qoldiramiz
    clean_text = ''.join(filter(str.isdigit, text))
    return float(clean_text) if clean_text else 0

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

# --- KLAVIATURALAR ---
def main_menu(user_id):
    kb = [
        [KeyboardButton(text="👥 Mijozlarim"), KeyboardButton(text="🔍 Qidirish")],
        [KeyboardButton(text="➕ Mijoz qo'shish"), KeyboardButton(text="📊 Statistika")],
        [KeyboardButton(text="⚠️ Muddat o'tganlar")]
    ]
    if user_id == ADMIN_ID:
        kb.append([KeyboardButton(text="👑 Admin Panel")])
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
    await message.answer("👤 Mijoz ismini kiriting:", reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="⬅️ Bekor qilish")]], resize_keyboard=True))
    await state.set_state(Form.adding_client)

@dp.message(Form.adding_client)
async def client_named(message: types.Message, state: FSMContext):
    if message.text == "⬅️ Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=main_menu(message.from_user.id))
        return
    
    now = get_uzb_time().strftime("%Y-%m-%d")
    conn = sqlite3.connect('debts.db')
    c = conn.cursor()
    c.execute("INSERT INTO clients (owner_id, name, last_update) VALUES (?, ?, ?)", (message.from_user.id, message.text, now))
    conn.commit()
    conn.close()
    await message.answer(f"✅ {message.text} qo'shildi!", reply_markup=main_menu(message.from_user.id))
    await state.clear()

@dp.message(F.text == "👥 Mijozlarim")
async def list_clients(message: types.Message):
    user_id = message.from_user.id
    conn = sqlite3.connect('debts.db')
    c = conn.cursor()
    c.execute("SELECT id, name, balance FROM clients WHERE owner_id=?", (user_id,))
    clients = c.fetchall()
    conn.close()
    
    if not clients:
        await message.answer("Hozircha mijozlar yo'q.")
        return
    
    buttons = [[InlineKeyboardButton(text=f"{cl[1]} | {format_num(cl[2])}", callback_data=f"view_{cl[0]}")] for cl in clients]
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer("📋 Mijozlaringiz ro'yxati:", reply_markup=kb)

@dp.callback_query(F.data == "back_to_list")
async def back_to_list_handler(callback: types.CallbackQuery):
    # Bu yerda user_id ni callback.from_user dan olamiz
    user_id = callback.from_user.id
    conn = sqlite3.connect('debts.db')
    c = conn.cursor()
    c.execute("SELECT id, name, balance FROM clients WHERE owner_id=?", (user_id,))
    clients = c.fetchall()
    conn.close()
    
    buttons = [[InlineKeyboardButton(text=f"{cl[1]} | {format_num(cl[2])}", callback_data=f"view_{cl[0]}")] for cl in clients]
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    await callback.message.edit_text("📋 Mijozlaringiz ro'yxati:", reply_markup=kb)

@dp.callback_query(F.data.startswith("view_"))
async def view_client(callback: types.CallbackQuery):
    c_id = callback.data.split("_")[1]
    conn = sqlite3.connect('debts.db')
    c = conn.cursor()
    c.execute("SELECT name, balance FROM clients WHERE id=?", (c_id,))
    cl = c.fetchone()
    conn.close()
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Sotuv (Qarz yozish)", callback_data=f"act_add_{c_id}")],
        [InlineKeyboardButton(text="✅ To'lov (Qarz ayirish)", callback_data=f"act_sub_{c_id}")],
        [InlineKeyboardButton(text="🔙 Orqaga qaytish", callback_data="back_to_list")]
    ])
    await callback.message.edit_text(f"👤 Mijoz: **{cl[0]}**\n💰 Joriy qarz: **{format_num(cl[1])}** so'm", reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data.startswith("act_"))
async def act_handler(callback: types.CallbackQuery, state: FSMContext):
    _, mode, c_id = callback.data.split("_")
    await state.update_data(c_id=c_id, mode=mode)
    
    text = "Kiriting: ➕ Qancha qarz qo'shildi?" if mode == 'add' else "Kiriting: ✅ Qancha to'lov qildi?"
    await callback.message.answer(f"{text}\n(Masalan: 500000 yoki 500 000)")
    await state.set_state(Form.amount_input)

@dp.message(Form.amount_input)
async def process_amount(message: types.Message, state: FSMContext):
    data = await state.get_data()
    try:
        amt = parse_num(message.text)
        if amt <= 0:
            await message.answer("Iltimos, 0 dan katta summa kiriting.")
            return

        mode = data['mode']
        db_amt = amt if mode == 'add' else -amt
        
        now_dt_obj = get_uzb_time()
        now_dt = now_dt_obj.strftime("%d.%m.%Y %H:%M")
        now_date = now_dt_obj.strftime("%Y-%m-%d")

        conn = sqlite3.connect('debts.db')
        c = conn.cursor()
        
        # Balansni yangilash
        c.execute("UPDATE clients SET balance = balance + ?, last_update = ? WHERE id = ?", (db_amt, now_date, data['c_id']))
        c.execute("INSERT INTO transactions (client_id, amount, type, date) VALUES (?, ?, ?, ?)", (data['c_id'], db_amt, mode, now_dt))
        
        # Yangi balansni ko'rish
        c.execute("SELECT name, balance FROM clients WHERE id = ?", (data['c_id'],))
        client_name, new_balance = c.fetchone()
        conn.commit()
        conn.close()
        
        chek = (
            f"✅ **AMALIYOT BAJARILDI**\n\n"
            f"👤 Mijoz: {client_name}\n"
            f"💰 Miqdor: {format_num(amt)} so'm\n"
            f"📝 Turi: {'Qarz qo`shildi ➕' if mode == 'add' else 'To`lov qilindi ✅'}\n"
            f"----------------------------\n"
            f"📉 **Yangi qoldiq: {format_num(new_balance)} so'm**"
        )
        
        await message.answer(chek, reply_markup=main_menu(message.from_user.id), parse_mode="Markdown")
        await state.clear()
        
    except Exception as e:
        await message.answer("❌ Xato! Faqat raqam kiriting.")

@dp.message(F.text == "📊 Statistika")
async def statistics(message: types.Message):
    conn = sqlite3.connect('debts.db')
    c = conn.cursor()
    c.execute("SELECT SUM(balance) FROM clients WHERE owner_id=?", (message.from_user.id,))
    total = c.fetchone()[0] or 0
    conn.close()
    await message.answer(f"📊 **Statistika**\n\n💰 Sizga bo'lgan jami qarz: **{format_num(total)}** so'm", parse_mode="Markdown")

# --- QOLGAN FUNKSIYALAR ---
# (Muddat o'tganlar va Admin panel kodingizdagi kabi qolaveradi)

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

Shu kodni update qilib raqamlarni qo’shib emas alohida joy tashlab masalan 5000000 emas 5 000 000 qilib yozadigan va summa qo’shadigan joyga son raqam va $ belgisi yoziladigan qilib tayyorlab ber