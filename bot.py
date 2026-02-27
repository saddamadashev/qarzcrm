import os
import asyncpg
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
DATABASE_URL = os.getenv("DATABASE_URL")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

db = None


async def connect_db():
    global db
    db = await asyncpg.connect(DATABASE_URL)

    await db.execute("""
    CREATE TABLE IF NOT EXISTS clients(
        id SERIAL PRIMARY KEY,
        name TEXT UNIQUE,
        debt FLOAT DEFAULT 0
    )
    """)


@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)

    keyboard.add("➕ Mijoz qo'shish")
    keyboard.add("💰 Qarz qo'shish")
    keyboard.add("💸 To'lov ayirish")
    keyboard.add("📋 Qarzdorlar")
    keyboard.add("📊 Hisobot")

    await message.answer("Qarz daftar bot", reply_markup=keyboard)


@dp.message_handler(lambda m: m.text == "➕ Mijoz qo'shish")
async def add_client(message: types.Message):
    await message.answer("Mijoz ismini yuboring")


@dp.message_handler(lambda m: m.text == "💰 Qarz qo'shish")
async def add_debt(message: types.Message):
    await message.answer("Format: Ism summa\nMasalan: Ali 50000")


@dp.message_handler(lambda m: m.text == "💸 To'lov ayirish")
async def pay_debt(message: types.Message):
    await message.answer("Format: Ism summa\nMasalan: Ali 20000")


@dp.message_handler(lambda m: m.text == "📋 Qarzdorlar")
async def list_clients(message: types.Message):

    rows = await db.fetch("SELECT name,debt FROM clients WHERE debt>0")

    if not rows:
        await message.answer("Qarzdorlar yo'q")
        return

    text = "Qarzdorlar:\n\n"

    for r in rows:
        text += f"{r['name']} — {r['debt']} so'm\n"

    await message.answer(text)


@dp.message_handler(lambda m: m.text == "📊 Hisobot")
async def report(message: types.Message):

    total = await db.fetchval("SELECT SUM(debt) FROM clients")

    if total is None:
        total = 0

    count = await db.fetchval("SELECT COUNT(*) FROM clients")

    text = f"""
📊 Hisobot

Mijozlar soni: {count}
Jami qarz: {total} so'm
"""

    await message.answer(text)


@dp.message_handler()
async def handle_messages(message: types.Message):

    text = message.text.split()

    if len(text) == 1:
        name = text[0]

        try:
            await db.execute(
                "INSERT INTO clients(name) VALUES($1)",
                name
            )

            await message.answer("Mijoz qo'shildi")

        except:
            await message.answer("Mijoz mavjud")

        return

    if len(text) == 2:

        name = text[0]
        amount = float(text[1])

        client = await db.fetchrow(
            "SELECT * FROM clients WHERE name=$1",
            name
        )

        if not client:
            await message.answer("Mijoz topilmadi")
            return

        await db.execute(
            "UPDATE clients SET debt=debt+$1 WHERE name=$2",
            amount,
            name
        )

        await message.answer("Qarz qo'shildi")


async def on_startup(dp):
    await connect_db()


if __name__ == "__main__":
    executor.start_polling(dp, on_startup=on_startup)