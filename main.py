import os
import asyncio
from datetime import datetime
import pytz
import asyncpg

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

db = None
state = {}
current_client = {}

tz = pytz.timezone("Asia/Tashkent")

async def init_db():
    global db
    db = await asyncpg.connect(DATABASE_URL)

    await db.execute("""
    CREATE TABLE IF NOT EXISTS clients(
        id SERIAL PRIMARY KEY,
        name TEXT
    )
    """)

    await db.execute("""
    CREATE TABLE IF NOT EXISTS debts(
        id SERIAL PRIMARY KEY,
        client_id INTEGER,
        amount FLOAT,
        type TEXT,
        created TIMESTAMP
    )
    """)

def main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Mijoz qo'shish")],
            [KeyboardButton(text="👥 Mijozlar")],
            [KeyboardButton(text="📊 Statistika")]
        ],
        resize_keyboard=True
    )

def client_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Qarz qo'shish")],
            [KeyboardButton(text="➖ Qarz ayirish")],
            [KeyboardButton(text="💰 Umumiy qarz")],
            [KeyboardButton(text="📜 Tarix")],
            [KeyboardButton(text="⬅️ Orqaga")]
        ],
        resize_keyboard=True
    )

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("Qarz CRM botga xush kelibsiz", reply_markup=main_menu())

@dp.message(lambda m: m.text == "➕ Mijoz qo'shish")
async def add_client(message: types.Message):
    state[message.from_user.id] = "add_client"
    await message.answer("Mijoz ismini yozing")

@dp.message(lambda m: state.get(m.from_user.id) == "add_client")
async def save_client(message: types.Message):

    await db.execute(
        "INSERT INTO clients(name) VALUES($1)",
        message.text
    )

    state.pop(message.from_user.id)

    await message.answer("Mijoz qo'shildi", reply_markup=main_menu())

@dp.message(lambda m: m.text == "👥 Mijozlar")
async def clients(message: types.Message):

    rows = await db.fetch("SELECT * FROM clients")

    keyboard = []

    for r in rows:
        keyboard.append([KeyboardButton(text=r["name"])])

    keyboard.append([KeyboardButton(text="⬅️ Orqaga")])

    await message.answer(
        "Mijozlar",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=keyboard,
            resize_keyboard=True
        )
    )

@dp.message(lambda m: m.text == "⬅️ Orqaga")
async def back(message: types.Message):
    await message.answer("Menu", reply_markup=main_menu())

@dp.message()
async def client_select(message: types.Message):

    row = await db.fetchrow(
        "SELECT * FROM clients WHERE name=$1",
        message.text
    )

    if row:

        current_client[message.from_user.id] = row["id"]

        await message.answer(
            f"{row['name']} tanlandi",
            reply_markup=client_menu()
        )

@dp.message(lambda m: m.text == "➕ Qarz qo'shish")
async def add_debt(message: types.Message):

    state[message.from_user.id] = "add_debt"

    await message.answer("Qarz summasini yozing")

@dp.message(lambda m: m.text == "➖ Qarz ayirish")
async def minus_debt(message: types.Message):

    state[message.from_user.id] = "minus_debt"

    await message.answer("To'langan summani yozing")

@dp.message(lambda m: state.get(m.from_user.id) == "add_debt")
async def save_debt(message: types.Message):

    try:
        amount = float(message.text)
    except:
        await message.answer("Faqat son yozing")
        return

    client_id = current_client.get(message.from_user.id)

    await db.execute(
        "INSERT INTO debts(client_id,amount,type,created) VALUES($1,$2,'add',$3)",
        client_id,
        amount,
        datetime.now(tz)
    )

    state.pop(message.from_user.id)

    await message.answer("Qarz qo'shildi")

@dp.message(lambda m: state.get(m.from_user.id) == "minus_debt")
async def save_minus(message: types.Message):

    try:
        amount = float(message.text)
    except:
        await message.answer("Faqat son yozing")
        return

    client_id = current_client.get(message.from_user.id)

    await db.execute(
        "INSERT INTO debts(client_id,amount,type,created) VALUES($1,$2,'minus',$3)",
        client_id,
        amount,
        datetime.now(tz)
    )

    state.pop(message.from_user.id)

    await message.answer("To'lov yozildi")

@dp.message(lambda m: m.text == "💰 Umumiy qarz")
async def total(message: types.Message):

    client_id = current_client.get(message.from_user.id)

    add = await db.fetchval(
        "SELECT COALESCE(SUM(amount),0) FROM debts WHERE client_id=$1 AND type='add'",
        client_id
    )

    minus = await db.fetchval(
        "SELECT COALESCE(SUM(amount),0) FROM debts WHERE client_id=$1 AND type='minus'",
        client_id
    )

    await message.answer(f"Umumiy qarz: {add-minus}")

@dp.message(lambda m: m.text == "📜 Tarix")
async def history(message: types.Message):

    client_id = current_client.get(message.from_user.id)

    rows = await db.fetch(
        "SELECT * FROM debts WHERE client_id=$1 ORDER BY created DESC LIMIT 20",
        client_id
    )

    if not rows:
        await message.answer("Tarix yo'q")
        return

    text = "So'nggi operatsiyalar:\n\n"

    for r in rows:

        sign = "➕" if r["type"] == "add" else "➖"

        date = r["created"].strftime("%d.%m.%Y %H:%M")

        text += f"{date} {sign} {r['amount']}\n"

    await message.answer(text)

@dp.message(lambda m: m.text == "📊 Statistika")
async def stats(message: types.Message):

    total = await db.fetchval("""
    SELECT COALESCE(SUM(
        CASE
        WHEN type='add' THEN amount
        ELSE -amount
        END
    ),0)
    FROM debts
    """)

    await message.answer(f"Umumiy qarz: {total}")

async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())