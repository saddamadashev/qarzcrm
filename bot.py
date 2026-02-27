import os
import asyncpg
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiogram.utils.keyboard import ReplyKeyboardBuilder
import asyncio

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
DATABASE_URL = os.getenv("DATABASE_URL")

bot = Bot(token=TOKEN)
dp = Dispatcher()

db = None


async def connect_db():
    global db
    db = await asyncpg.connect(DATABASE_URL)

    await db.execute("""
    CREATE TABLE IF NOT EXISTS clients(
        id SERIAL PRIMARY KEY,
        name TEXT,
        debt FLOAT
    )
    """)


menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="➕ Mijoz qo'shish")],
        [KeyboardButton(text="💰 Qarzni qo'shish")],
        [KeyboardButton(text="➖ Qarzni ayirish")],
        [KeyboardButton(text="📋 Qarzdorlar")],
        [KeyboardButton(text="📊 Hisobot")]
    ],
    resize_keyboard=True
)


@dp.message(Command("start"))
async def start(message: types.Message):

    if message.from_user.id != ADMIN_ID:
        await message.answer("Siz admin emassiz")
        return

    await message.answer(
        "Qarz daftar botga xush kelibsiz",
        reply_markup=menu
    )


# MIJOZ QO'SHISH

@dp.message(lambda m: m.text == "➕ Mijoz qo'shish")
async def add_client(message: types.Message):

    await message.answer("Mijoz ismini yozing")

    dp.message.register(save_client)


async def save_client(message: types.Message):

    name = message.text

    await db.execute(
        "INSERT INTO clients(name,debt) VALUES($1,$2)",
        name,
        0
    )

    await message.answer("Mijoz qo'shildi", reply_markup=menu)

    dp.message.unregister(save_client)


# QARZ QO'SHISH

@dp.message(lambda m: m.text == "💰 Qarzni qo'shish")
async def add_debt(message: types.Message):

    clients = await db.fetch("SELECT * FROM clients")

    text = "Mijoz tanlang:\n"

    for c in clients:
        text += f"{c['id']} - {c['name']}\n"

    await message.answer(text)

    dp.message.register(debt_client)


async def debt_client(message: types.Message):

    global selected_client

    selected_client = int(message.text)

    await message.answer("Summani yozing")

    dp.message.register(save_debt)


async def save_debt(message: types.Message):

    amount = float(message.text)

    await db.execute(
        "UPDATE clients SET debt = debt + $1 WHERE id=$2",
        amount,
        selected_client
    )

    await message.answer("Qarz qo'shildi", reply_markup=menu)

    dp.message.unregister(save_debt)


# QARZ AYIRISH

@dp.message(lambda m: m.text == "➖ Qarzni ayirish")
async def minus_debt(message: types.Message):

    clients = await db.fetch("SELECT * FROM clients")

    text = "Mijoz tanlang:\n"

    for c in clients:
        text += f"{c['id']} - {c['name']}\n"

    await message.answer(text)

    dp.message.register(minus_client)


async def minus_client(message: types.Message):

    global selected_client

    selected_client = int(message.text)

    await message.answer("To'langan summa")

    dp.message.register(save_minus)


async def save_minus(message: types.Message):

    amount = float(message.text)

    await db.execute(
        "UPDATE clients SET debt = debt - $1 WHERE id=$2",
        amount,
        selected_client
    )

    await message.answer("Qarz kamaytirildi", reply_markup=menu)

    dp.message.unregister(save_minus)


# QARZDORLAR

@dp.message(lambda m: m.text == "📋 Qarzdorlar")
async def debtors(message: types.Message):

    clients = await db.fetch("SELECT * FROM clients")

    text = "Qarzdorlar:\n\n"

    for c in clients:
        text += f"{c['name']} - {c['debt']}\n"

    await message.answer(text)


# HISOBOT

@dp.message(lambda m: m.text == "📊 Hisobot")
async def report(message: types.Message):

    total = await db.fetchval("SELECT SUM(debt) FROM clients")

    if total is None:
        total = 0

    await message.answer(f"Umumiy qarz: {total}")


async def main():

    await connect_db()

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())