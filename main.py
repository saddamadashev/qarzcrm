import logging
import sqlite3
import asyncio
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# --- SOZLAMALAR ---
TOKEN = "8759158410:AAFjHdOY5R95WlC0GG4n5dG7koRTPvv68jE"
ADMIN_ID = 565876427

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- BAZA BILAN ISHLASH ---
def db(q, p=(), fetch=False):
    conn = sqlite3.connect("debt.db")
    cur = conn.cursor()
    try:
        cur.execute(q, p)
        r = cur.fetchall() if fetch else None
        conn.commit()
    finally:
        conn.close()
    return r

def init():
    db("CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY)")
    db("CREATE TABLE IF NOT EXISTS clients(id INTEGER PRIMARY KEY AUTOINCREMENT, owner INTEGER, name TEXT, debt REAL DEFAULT 0)")
    db("CREATE TABLE IF NOT EXISTS history(id INTEGER PRIMARY KEY AUTOINCREMENT, client_id INTEGER, amount REAL, type TEXT, date TEXT)")

init()

# --- FORMATLASH ---
def money(x):
    if x is None: x = 0
    return f"{x:,.0f}".replace(",", " ")

# --- HOLATLAR ---
class S(StatesGroup):
    client = State()
    amount = State()
    search = State()

# --- KLAVIATURA ---
def main_kb(user_id):
    kb = [
        [KeyboardButton(text="👤 Mijozlar"), KeyboardButton(text="➕ Mijoz qo'shish")],
        [KeyboardButton(text="🔎 Qidirish"), KeyboardButton(text="📊 Hisobot")]
    ]
    if user_id == ADMIN_ID:
        kb.append([KeyboardButton(text="⚙️ Admin")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

# --- START ---
@dp.message(Command("start"))
async def start(m: types.Message):
    db("INSERT OR IGNORE INTO users VALUES(?)", (m.from_user.id,))
    await m.answer("📒 Xush kelibsiz!", reply_markup=main_kb(m.from_user.id))

# --- MIJOZ QO'SHISH ---
@dp.message(F.text == "➕ Mijoz qo'shish")
async def add_client(m: types.Message, state: FSMContext):
    await m.answer("Mijoz ismini yuboring:")
    await state.set_state(S.client)

@dp.message(S.client)
async def save_client(m: types.Message, state: FSMContext):
    db("INSERT INTO clients(owner, name) VALUES(?,?)", (m.from_user.id, m.text))
    await state.clear()
    await m.answer("✅ Qo'shildi", reply_markup=main_kb(m.from_user.id))

# --- MIJOZLAR RO'YXATI ---
@dp.message(F.text == "👤 Mijozlar")
async def list_clients(m: types.Message):
    rows = db("SELECT id, name, debt FROM clients WHERE owner=?", (m.from_user.id,), True)
    if not rows: return await m.answer("Mijozlar yo'q")
    
    kb = InlineKeyboardBuilder()
    for i in rows:
        kb.row(InlineKeyboardButton(text=f"{i[1]} | {money(i[2])}", callback_data=f"cl_{i[0]}"))
    await m.answer("Mijozni tanlang:", reply_markup=kb.as_markup())

@dp.callback_query(F.data.startswith("cl_"))
async def view_client(c: types.CallbackQuery, state: FSMContext):
    cid = c.data.split("_")[1]
    res = db("SELECT name, debt FROM clients WHERE id=?", (cid,), True)
    if not res: return await c.answer("Topilmadi")
    
    await state.update_data(cid=cid)
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="➕ Qarz", callback_data="add"), InlineKeyboardButton(text="➖ To'lov", callback_data="sub"))
    kb.row(InlineKeyboardButton(text="📜 Tarix", callback_data="hist"), InlineKeyboardButton(text="🗑 O'chirish", callback_data="del"))
    
    await c.message.edit_text(f"👤 {res[0][0]}\n💰 Qarz: {money(res[0][1])} so'm", reply_markup=kb.as_markup())

# --- QARZ / TO'LOV ---
@dp.callback_query(F.data.in_(["add", "sub"]))
async def ask_amount(c: types.CallbackQuery, state: FSMContext):
    await state.update_data(action=c.data)
    await c.message.answer("Summani yozing:")
    await state.set_state(S.amount)

@dp.message(S.amount)
async def process_amount(m: types.Message, state: FSMContext):
    try:
        val = float(m.text)
    except:
        return await m.answer("Faqat raqam yozing!")

    data = await state.get_data()
    cid, act = data.get("cid"), data.get("action")
    
    if act == "add":
        db("UPDATE clients SET debt = debt + ? WHERE id = ?", (val, cid))
        t = "Qarz"
    else:
        db("UPDATE clients SET debt = debt - ? WHERE id = ?", (val, cid))
        t = "To'lov"

    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    db("INSERT INTO history(client_id, amount, type, date) VALUES(?,?,?,?)", (cid, val, t, now))
    
    res = db("SELECT name, debt FROM clients WHERE id=?", (cid,), True)[0]
    await m.answer(f"👤 {res[0]}\n💰 {money(val)} so'm {t}\n💳 Qoldiq: {money(res[1])}", reply_markup=main_kb(m.from_user.id))
    await state.clear()

# --- QIDIRUV VA HISOBOT ---
@dp.message(F.text == "🔎 Qidirish")
async def search_start(m: types.Message, state: FSMContext):
    await m.answer("Ism kiriting:")
    await state.set_state(S.search)

@dp.message(S.search)
async def search_run(m: types.Message, state: FSMContext):
    rows = db("SELECT name, debt FROM clients WHERE name LIKE ? AND owner=?", (f"%{m.text}%", m.from_user.id), True)
    txt = "\n".join([f"{r[0]} | {money(r[1])}" for r in rows]) if rows else "Topilmadi"
    await m.answer(txt)
    await state.clear()

@dp.message(F.text == "📊 Hisobot")
async def report(m: types.Message):
    res = db("SELECT COUNT(*), SUM(debt) FROM clients WHERE owner=?", (m.from_user.id,), True)[0]
    await m.answer(f"👥 Mijozlar: {res[0]}\n💰 Jami qarz: {money(res[1])} so'm")

# --- ADMIN ---
@dp.message(F.text == "⚙️ Admin")
async def admin_panel(m: types.Message):
    if m.from_user.id != ADMIN_ID: return
    u = db("SELECT COUNT(*) FROM users", fetch=True)[0][0]
    d = db("SELECT SUM(debt) FROM clients", fetch=True)[0][0]
    await m.answer(f"👑 Admin\n👤 Foydalanuvchilar: {u}\n💰 Umumiy qarz: {money(d)}")

# --- ASOSIY ISHGA TUSHIRISH ---
async def main():
    # Railway-dagi 'Conflict' xatosini yo'qotish uchun:
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot to'xtatildi")
