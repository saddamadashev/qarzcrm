import os
import asyncpg
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils import executor

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

db = None

menu = ReplyKeyboardMarkup(resize_keyboard=True)
menu.add(
    KeyboardButton("➕ Mijoz qo'shish"),
    KeyboardButton("💰 Qarz qo'shish")
)
menu.add(
    KeyboardButton("➖ Qarz ayirish"),
    KeyboardButton("📋 Qarzdorlar")
)
menu.add(
    KeyboardButton("📊 Hisobot")
)


async def connect_db():
    global db
    db = await asyncpg.connect(os.getenv("DATABASE_URL"))

    await db.execute("""
    CREATE TABLE IF NOT EXISTS clients(
        id SERIAL PRIMARY KEY,
        name TEXT,
        debt FLOAT DEFAULT 0
    )
    """)


@dp.message_handler(commands=['start'])
async def start(message: types.Message):

    if message.from_user.id != ADMIN_ID:
        return

    await message.answer(
        "📊 Qarz CRM botiga xush kelibsiz",
        reply_markup=menu
    )


@dp.message_handler(lambda m: m.text == "➕ Mijoz qo'shish")
async def add_client(message: types.Message):

    await message.answer("Mijoz ismini yuboring")


@dp.message_handler(lambda m: m.text and m.text.startswith("mijoz "))
async def add_client_db(message: types.Message):

    name = message.text.replace("mijoz ", "")

    await db.execute(
        "INSERT INTO clients(name) VALUES($1)",
        name
    )

    await message.answer("✅ Mijoz qo'shildi")


@dp.message_handler(lambda m: m.text == "📋 Qarzdorlar")
async def list_clients(message: types.Message):

    rows = await db.fetch("SELECT * FROM clients")

    if not rows:
        await message.answer("Qarzdor yo'q")
        return

    text = "📋 Qarzdorlar:\n\n"

    for r in rows:
        text += f"{r['name']} — {r['debt']} so'm\n"

    await message.answer(text)


@dp.message_handler(lambda m: m.text == "📊 Hisobot")
async def report(message: types.Message):

    total = await db.fetchval("SELECT SUM(debt) FROM clients")

    if total is None:
        total = 0

    await message.answer(
        f"📊 Umumiy qarz: {total} so'm"
    )


@dp.message_handler()
async def handle_messages(message: types.Message):

    text = message.text.split()

    if len(text) < 3:
        return

    command = text[0]
    name = text[1]
    amount = float(text[2])

    client = await db.fetchrow(
        "SELECT * FROM clients WHERE name=$1",
        name
    )

    if not client:
        await message.answer("❌ Mijoz topilmadi")
        return

    if command == "+":
        new = client["debt"] + amount

    elif command == "-":
        new = client["debt"] - amount

    else:
        return

    await db.execute(
        "UPDATE clients SET debt=$1 WHERE name=$2",
        new,
        name
    )

    await message.answer(
        f"✅ {name} qarzi: {new}"
    )


async def on_startup(dp):
    await connect_db()


if __name__ == "__main__":
    executor.start_polling(
        dp,
        on_startup=on_startup
    )