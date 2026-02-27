import os
import asyncpg
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
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
        telegram_id BIGINT,
        debt FLOAT DEFAULT 0
    )
    """)

    await db.execute("""
    CREATE TABLE IF NOT EXISTS payments(
        id SERIAL PRIMARY KEY,
        client_id INTEGER,
        amount FLOAT,
        type TEXT,
        created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)


menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="➕ Mijoz qo'shish")],
        [KeyboardButton(text="💰 Qarz qo'shish")],
        [KeyboardButton(text="➖ To'lov ayirish")],
        [KeyboardButton(text="📊 Hisobot")],
    ],
    resize_keyboard=True
)


@dp.message(Command("start"))
async def start(message: types.Message):

    if message.from_user.id == ADMIN_ID:
        await message.answer("Admin panel", reply_markup=menu)
    else:
        await message.answer("Botga xush kelibsiz\n/qarzim yozib qarzingizni ko'ring")


@dp.message(Command("qarzim"))
async def my_debt(message: types.Message):

    client = await db.fetchrow(
        "SELECT * FROM clients WHERE telegram_id=$1",
        message.from_user.id
    )

    if not client:
        await message.answer("Siz bazada topilmadingiz")
        return

    await message.answer(
        f"Sizning qarzingiz: {client['debt']} so'm"
    )


@dp.message(lambda m: m.text == "➕ Mijoz qo'shish")
async def add_client(message: types.Message):

    if message.from_user.id != ADMIN_ID:
        return

    await message.answer(
        "Format:\nIsm TelegramID\n\nMasalan:\nAli 123456789"
    )


@dp.message(lambda m: len(m.text.split()) == 2)
async def save_client(message: types.Message):

    if message.from_user.id != ADMIN_ID:
        return

    name, tg_id = message.text.split()

    await db.execute(
        "INSERT INTO clients(name,telegram_id) VALUES($1,$2)",
        name, int(tg_id)
    )

    await message.answer("Mijoz qo'shildi")


@dp.message(lambda m: m.text == "📊 Hisobot")
async def report(message: types.Message):

    rows = await db.fetch(
        "SELECT * FROM clients ORDER BY debt DESC"
    )

    text = "📊 Qarzdorlar:\n\n"

    for r in rows:
        text += f"{r['name']} - {r['debt']} so'm\n"

    await message.answer(text)


async def main():

    await connect_db()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
    print("NEW VERSION WORKING")
    