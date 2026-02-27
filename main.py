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
ADMIN_ID = 12345678  # BU YERGA O'ZINGIZNING ID-INGIZNI YOZING

bot = Bot(token=TOKEN)
dp = Dispatcher()

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
    await message.answer("🚀 Multi-User Savdo va Qarz Tizimiga xush kelibsiz!", 
                         reply_markup=main_menu(message.from_user.id))

# 1. Mijoz qo'shish
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

# 2. Mijozlar ro'yxati va qidiruv
@dp.message(F.text == "👥 Mijozlarim")
async def list_clients(message: types.Message):
    conn = sqlite3.connect('debts.db')
    c = conn.cursor()
    c.execute("SELECT id, name, balance FROM clients WHERE owner_id=?", (message.from_user.id,))
    clients = c.fetchall()
    conn.close()
    if not clients:
        await message.answer("Mijozlar yo'q.")
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"{cl[1]} | {cl[2]:.1f}", callback_data=f"view_{cl[0]}")] for cl in clients])
    await message.answer("📋 Ro'yxat:", reply_markup=kb)

@dp.message(F.text == "🔍 Qidirish")
async def search_start(message: types.Message, state: FSMContext):
    await message.answer("🔎 Ismni kiriting:")
    await state.set_state(Form.searching)

@dp.message(Form.searching)
async def search_done(message: types.Message, state: FSMContext):
    conn = sqlite3.connect('debts.db')
    c = conn.cursor()
    c.execute("SELECT id, name, balance FROM clients WHERE owner_id=? AND name LIKE ?", (message.from_user.id, f"%{message.text}%"))
    res = c.fetchall()
    conn.close()
    if res:
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"{r[1]} | {r[2]}", callback_data=f"view_{r[0]}")] for r in res])
        await message.answer("Topildi:", reply_markup=kb)
    else:
        await message.answer("Hech kim topilmadi.")
    await state.clear()

# 3. Hisob-kitob (Qo'shish/Ayirish)
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
    await callback.message.edit_text(f"👤 {cl[0]}\n💰 Qarzi: {cl[1]:.2f}", reply_markup=kb)

@dp.callback_query(F.data.startswith("act_"))
async def act(callback: types.CallbackQuery, state: FSMContext):
    _, mode, c_id = callback.data.split("_")
    await state.update_data(c_id=c_id, mode=mode)
    await callback.message.answer("💳 Summani kiriting:")
    await state.set_state(Form.amount_input)

@dp.message(Form.amount_input)
async def process_amount(message: types.Message, state: FSMContext):
    data = await state.get_data()
    try:
        amt = float(message.text)
        if data['mode'] == 'sub': amt = -amt
        now_dt = datetime.now().strftime("%Y-%m-%d %H:%M")
        now_date = datetime.now().strftime("%Y-%m-%d")
        conn = sqlite3.connect('debts.db')
        c = conn.cursor()
        c.execute("UPDATE clients SET balance = balance + ?, last_update = ? WHERE id = ?", (amt, now_date, data['c_id']))
        c.execute("INSERT INTO transactions (client_id, amount, type, date) VALUES (?, ?, ?, ?)", (data['c_id'], amt, data['mode'], now_dt))
        conn.commit()
        conn.close()
        await message.answer(f"✅ Bajarildi! Vaqt: {now_dt}", reply_markup=main_menu(message.from_user.id))
    except:
        await message.answer("Faqat raqam kiriting!")
    await state.clear()

# 4. Muddat o'tganlar (30 kundan beri to'lov qilmaganlar)
@dp.message(F.text == "⚠️ Muddat o'tganlar")
async def expired_debts(message: types.Message):
    month_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    conn = sqlite3.connect('debts.db')
    c = conn.cursor()
    c.execute("SELECT name, balance, last_update FROM clients WHERE owner_id=? AND balance > 0 AND last_update < ?", (message.from_user.id, month_ago))
    res = c.fetchall()
    conn.close()
    if not res:
        await message.answer("Hozircha muddat o'tgan qarzlar yo'q. Baraka toping!")
    else:
        text = "⚠️ **30 kundan beri to'lanmagan qarzlar:**\n\n"
        for r in res:
            text += f"👤 {r[0]} | 💰 {r[1]} so'm\n(Oxirgi marta: {r[2]})\n\n"
        await message.answer(text, parse_mode="Markdown")

# 5. Admin Funksiyalar
@dp.message(F.text == "👑 Admin Panel")
async def admin_stat(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    conn = sqlite3.connect('debts.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    u_count = c.fetchone()[0]
    c.execute("SELECT SUM(balance) FROM clients")
    total = c.fetchone()[0] or 0
    conn.close()
    await message.answer(f"📊 **Admin Panel**\n\n👥 Foydalanuvchilar: {u_count}\n💰 Tizimdagi jami qarz: {total:.2f}")

@dp.message(F.text == "📢 Xabar yuborish")
async def broadcast_start(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await message.answer("Barcha foydalanuvchilarga yuboriladigan xabarni yozing:")
    await state.set_state(Form.broadcast)

@dp.message(Form.broadcast)
async def broadcast_done(message: types.Message, state: FSMContext):
    conn = sqlite3.connect('debts.db')
    c = conn.cursor()
    c.execute("SELECT user_id FROM users")
    users = c.fetchall()
    conn.close()
    for u in users:
        try: await bot.send_message(u[0], f"📣 **ADMIN XABARI:**\n\n{message.text}", parse_mode="Markdown")
        except: continue
    await message.answer("Xabar yuborildi.")
    await state.clear()

@dp.callback_query(F.data == "back_to_list")
async def back(callback: types.CallbackQuery):
    await list_clients(callback.message)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())