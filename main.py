import logging  # 'Import' emas, 'import' bo'lishi kerak
import sqlite3
import asyncio
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# TOKENni xavfsizlik uchun ehtiyot qiling!
TOKEN = "8759158410:AAFjHdOY5R95WlC0GG4n5dG7koRTPvv68jE"
ADMIN_ID = 565876427

logging.basicConfig(level=logging.INFO)

bot = Bot(token=TOKEN)
dp = Dispatcher()

# ----------- MONEY FORMAT -----------
def money(x):
    if x is None: x = 0
    return f"{x:,.0f}".replace(",", " ")

# ----------- DATABASE -----------
def db(q, p=(), fetch=False):
    conn = sqlite3.connect("debt.db")
    cur = conn.cursor()
    cur.execute(q, p)
    r = cur.fetchall() if fetch else None
    conn.commit()
    conn.close()
    return r

def init():
    db("""CREATE TABLE IF NOT EXISTS users(
    id INTEGER PRIMARY KEY)""")

    db("""CREATE TABLE IF NOT EXISTS clients(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner INTEGER,
    name TEXT,
    debt REAL DEFAULT 0)""")

    db("""CREATE TABLE IF NOT EXISTS history(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER,
    amount REAL,
    type TEXT,
    date TEXT)""")

init()

# ----------- STATES -----------
class S(StatesGroup):
    client = State()
    amount = State()
    search = State()

# ----------- KEYBOARD -----------
def main_kb(user_id):
    kb = [
        [KeyboardButton(text="👤 Mijozlar"), KeyboardButton(text="➕ Mijoz qo'shish")],
        [KeyboardButton(text="🔎 Qidirish"), KeyboardButton(text="📊 Hisobot")]
    ]
    if user_id == ADMIN_ID:
        kb.append([KeyboardButton(text="⚙️ Admin")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

# ----------- START -----------
@dp.message(Command("start"))
async def start(m: types.Message):
    db("INSERT OR IGNORE INTO users VALUES(?)", (m.from_user.id,))
    await m.answer(
        "📒 Professional Qarzdor Botga xush kelibsiz",
        reply_markup=main_kb(m.from_user.id)
    )

# ----------- ADD CLIENT -----------
@dp.message(F.text == "➕ Mijoz qo'shish")
async def add_client(m: types.Message, state: FSMContext):
    await m.answer("Mijoz ismini yuboring")
    await state.set_state(S.client)

@dp.message(S.client)
async def save_client(m: types.Message, state: FSMContext):
    db(
        "INSERT INTO clients(owner,name) VALUES(?,?)",
        (m.from_user.id, m.text)
    )
    await state.clear()
    await m.answer("✅ Mijoz qo'shildi", reply_markup=main_kb(m.from_user.id))

# ----------- CLIENT LIST -----------
@dp.message(F.text == "👤 Mijozlar")
async def clients(m: types.Message):
    rows = db(
        "SELECT id,name,debt FROM clients WHERE owner=?",
        (m.from_user.id,),
        True
    )
    if not rows:
        return await m.answer("Mijoz yo'q")
    kb = InlineKeyboardBuilder()
    for i in rows:
        kb.row(
            InlineKeyboardButton(
                text=f"{i[1]} | {money(i[2])}",
                callback_data=f"client_{i[0]}"
            )
        )
    await m.answer("Mijozni tanlang", reply_markup=kb.as_markup())

# ----------- CLIENT VIEW -----------
@dp.callback_query(F.data.startswith("client_"))
async def view(c: types.CallbackQuery, state: FSMContext):
    cid = c.data.split("_")[1]
    res = db("SELECT name,debt FROM clients WHERE id=?", (cid,), True)
    if not res:
        return await c.answer("Mijoz topilmadi")
    
    client = res[0]
    await state.update_data(cid=cid)
    
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="➕ Qarz", callback_data="add"),
        InlineKeyboardButton(text="➖ To'lov", callback_data="sub")
    )
    kb.row(
        InlineKeyboardButton(text="📜 Tarix", callback_data="history"),
        InlineKeyboardButton(text="🗑 O'chirish", callback_data="del")
    )
    text = f"👤 {client[0]}\n\n💰 Qarz: {money(client[1])} so'm"
    await c.message.edit_text(text, reply_markup=kb.as_markup())

# ----------- ADD / SUB -----------
@dp.callback_query(F.data.in_(["add", "sub"]))
async def change(c: types.CallbackQuery, state: FSMContext):
    await state.update_data(action=c.data)
    await c.message.answer("Summani yuboring")
    await state.set_state(S.amount)

@dp.message(S.amount)
async def amount(m: types.Message, state: FSMContext):
    try:
        a = float(m.text)
    except:
        return await m.answer("Raqam yuboring")

    data = await state.get_data()
    cid = data.get("cid")
    act = data.get("action")

    if not cid:
        return await m.answer("Xatolik: Mijoz tanlanmagan")

    if act == "add":
        db("UPDATE clients SET debt=debt+? WHERE id=?", (a, cid))
        typ = "Qarz"
    else:
        db("UPDATE clients SET debt=debt-? WHERE id=?", (a, cid))
        typ = "To'lov"

    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    db("INSERT INTO history(client_id,amount,type,date) VALUES(?,?,?,?)", (cid, a, typ, now))

    res = db("SELECT name,debt FROM clients WHERE id=?", (cid,), True)[0]
    txt = f"🧾 Chek\n\n👤 {res[0]}\n\n💰 {money(a)} so'm\n📝 {typ}\n📅 {now}\n\n💳 Qoldiq: {money(res[1])}"
    
    await state.clear()
    await m.answer(txt, reply_markup=main_kb(m.from_user.id))

# ----------- HISTORY -----------
@dp.callback_query(F.data == "history")
async def history(c: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    cid = data.get("cid")
    if not cid:
        return await c.answer("Mijoz aniqlanmadi")

    rows = db("SELECT amount,type,date FROM history WHERE client_id=? ORDER BY id DESC LIMIT 10", (cid,), True)
    if not rows:
        return await c.answer("Tarix bo'sh")

    text = "📜 Oxirgi 10 amal\n\n"
    for r in rows:
        text += f"{r[1]} | {money(r[0])} | {r[2]}\n"
    await c.message.answer(text)

# ----------- DELETE CLIENT -----------
@dp.callback_query(F.data == "del")
async def delete(c: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    cid = data.get("cid")
    db("DELETE FROM clients WHERE id=?", (cid,))
    db("DELETE FROM history WHERE client_id=?", (cid,)) # Tarixni ham o'chirish yaxshiroq
    await c.message.answer("🗑 Mijoz o'chirildi")
    await state.clear()

# ----------- SEARCH -----------
@dp.message(F.text == "🔎 Qidirish")
async def search(m: types.Message, state: FSMContext):
    await m.answer("Ism yozing")
    await state.set_state(S.search)

@dp.message(S.search)
async def find(m: types.Message, state: FSMContext):
    rows = db("SELECT name,debt FROM clients WHERE name LIKE ? AND owner=?", (f"%{m.text}%", m.from_user.id), True)
    if not rows:
        await state.clear()
        return await m.answer("Topilmadi")
    t = "🔎 Qidiruv natijalari:\n\n"
    for r in rows:
        t += f"{r[0]} | {money(r[1])}\n"
    await state.clear()
    await m.answer(t)

# ----------- REPORT -----------
@dp.message(F.text == "📊 Hisobot")
async def report(m: types.Message):
    res_total = db("SELECT SUM(debt) FROM clients WHERE owner=?", (m.from_user.id,), True)[0][0]
    total = res_total if res_total else 0
    res_count = db("SELECT COUNT(*) FROM clients WHERE owner=?", (m.from_user.id,), True)[0][0]
    count = res_count if res_count else 0
    await m.answer(f"📊 Hisobot\n\n👥 Mijozlar: {count}\n💰 Jami qarz: {money(total)} so'm")

# ----------- ADMIN -----------
@dp.message(F.text == "⚙️ Admin")
async def admin(m: types.Message):
    if m.from_user.id != ADMIN_ID:
        return
    users = db("SELECT COUNT(*) FROM users", fetch=True)[0][0]
    res_debts = db("SELECT SUM(debt) FROM clients", fetch=True)[0][0]
    debts = res_debts if res_debts else 0
    await m.answer(f"👑 ADMIN\n\n👥 Foydalanuvchilar: {users}\n💰 Tizim qarzi: {money(debts)}")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
