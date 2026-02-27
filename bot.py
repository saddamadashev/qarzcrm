import os
import asyncio
from datetime import datetime
import asyncpg

from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

db = None
user_states = {}
selected_client = {}

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
        date TIMESTAMP
    )
    """)

def main_menu():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("➕ Mijoz qo'shish")
    kb.add("👥 Mijozlar")
    kb.add("📊 Statistika")
    return kb

def client_menu():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("➕ Qarz qo'shish")
    kb.add("➖ Qarz ayirish")
    kb.add("💰 Umumiy qarz")
    kb.add("📜 Tarix")
    kb.add("⬅️ Orqaga")
    return kb

@dp.message(commands=["start"])
async def start(message: types.Message):
    await message.answer("Qarz CRM botga xush kelibsiz", reply_markup=main_menu())

@dp.message(lambda m: m.text == "➕ Mijoz qo'shish")
async def add_client(message: types.Message):
    user_states[message.from_user.id] = "add_client"
    await message.answer("Mijoz ismini yuboring")

@dp.message(lambda m: user_states.get(m.from_user.id) == "add_client")
async def save_client(message: types.Message):
    await db.execute("INSERT INTO clients(name) VALUES($1)", message.text)

    user_states.pop(message.from_user.id)
    await message.answer("Mijoz qo'shildi", reply_markup=main_menu())

@dp.message(lambda m: m.text == "👥 Mijozlar")
async def clients(message: types.Message):

    rows = await db.fetch("SELECT * FROM clients")

    kb = ReplyKeyboardMarkup(resize_keyboard=True)

    for r in rows:
        kb.add(r["name"])

    kb.add("⬅️ Orqaga")

    await message.answer("Mijozlar", reply_markup=kb)

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
        selected_client[message.from_user.id] = row["id"]

        await message.answer(
            f"{row['name']} tanlandi",
            reply_markup=client_menu()
        )

@dp.message(lambda m: m.text == "➕ Qarz qo'shish")
async def debt_add(message: types.Message):

    user_states[message.from_user.id] = "add_debt"
    await message.answer("Qarz summasini yuboring")

@dp.message(lambda m: m.text == "➖ Qarz ayirish")
async def debt_minus(message: types.Message):

    user_states[message.from_user.id] = "minus_debt"
    await message.answer("Qaytarilgan summani yuboring")

@dp.message(lambda m: user_states.get(m.from_user.id) == "add_debt")
async def save_debt(message: types.Message):

    amount = float(message.text)
    client = selected_client.get(message.from_user.id)

    await db.execute("""
    INSERT INTO debts(client_id,amount,type,date)
    VALUES($1,$2,'add',$3)
    """, client, amount, datetime.now())

    user_states.pop(message.from_user.id)

    await message.answer("Qarz qo'shildi")

@dp.message(lambda m: user_states.get(m.from_user.id) == "minus_debt")
async def minus_debt(message: types.Message):

    amount = float(message.text)
    client = selected_client.get(message.from_user.id)

    await db.execute("""
    INSERT INTO debts(client_id,amount,type,date)
    VALUES($1,$2,'minus',$3)
    """, client, amount, datetime.now())

    user_states.pop(message.from_user.id)

    await message.answer("Qarz kamaytirildi")

@dp.message(lambda m: m.text == "💰 Umumiy qarz")
async def total_debt(message: types.Message):

    client = selected_client.get(message.from_user.id)

    add = await db.fetchval("""
    SELECT COALESCE(SUM(amount),0)
    FROM debts
    WHERE client_id=$1 AND type='add'
    """, client)

    minus = await db.fetchval("""
    SELECT COALESCE(SUM(amount),0)
    FROM debts
    WHERE client_id=$1 AND type='minus'
    """, client)

    total = add - minus

    await message.answer(f"Umumiy qarz: {total}")

@dp.message(lambda m: m.text == "📜 Tarix")
async def history(message: types.Message):

    client = selected_client.get(message.from_user.id)

    rows = await db.fetch("""
    SELECT * FROM debts
    WHERE client_id=$1
    ORDER BY date DESC
    LIMIT 10
    """, client)

    text = ""

    for r in rows:

        sign = "➕" if r["type"] == "add" else "➖"

        text += f"{r['date']} {sign} {r['amount']}\n"

    if text == "":
        text = "Tarix yo'q"

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