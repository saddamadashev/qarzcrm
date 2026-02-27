import os
import asyncpg
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
from aiogram.filters import Command
from aiogram import F
import asyncio

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

db = None

# DATABASE ULANISH
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

# START
@dp.message(Command("start"))
async def start(message: Message):
    await message.answer(
        "📒 Qarz daftar bot\n\n"
        "Buyruqlar:\n"
        "/add Ism Summa\n"
        "/pay Ism Summa\n"
        "/list\n"
        "/check Ism\n"
        "/help"
    )

# HELP
@dp.message(Command("help"))
async def help_cmd(message: Message):
    await message.answer(
        "📌 Buyruqlar:\n\n"
        "/add Ali 50000 → qarz qo'shish\n"
        "/pay Ali 20000 → qarz kamaytirish\n"
        "/check Ali → qarz ko'rish\n"
        "/list → barcha qarzdorlar\n"
    )

# QARZ QO'SHISH
@dp.message(Command("add"))
async def add_debt(message: Message):

    try:
        _, name, amount = message.text.split()
        amount = float(amount)
    except:
        await message.answer("❌ Format:\n/add Ali 50000")
        return

    client = await db.fetchrow(
        "SELECT * FROM clients WHERE name=$1", name)

    if client:
        await db.execute(
            "UPDATE clients SET debt=debt+$1 WHERE name=$2",
            amount, name)
    else:
        await db.execute(
            "INSERT INTO clients(name,debt) VALUES($1,$2)",
            name, amount)

    await message.answer(f"✅ {name} ga {amount} qo'shildi")

# QARZ KAMAYTIRISH
@dp.message(Command("pay"))
async def pay_debt(message: Message):

    try:
        _, name, amount = message.text.split()
        amount = float(amount)
    except:
        await message.answer("❌ Format:\n/pay Ali 20000")
        return

    client = await db.fetchrow(
        "SELECT * FROM clients WHERE name=$1", name)

    if not client:
        await message.answer("❌ Mijoz topilmadi")
        return

    await db.execute(
        "UPDATE clients SET debt=debt-$1 WHERE name=$2",
        amount, name)

    await message.answer(f"💰 {name} {amount} to'ladi")

# BITTA MIJOZ
@dp.message(Command("check"))
async def check_debt(message: Message):

    try:
        _, name = message.text.split()
    except:
        await message.answer("❌ Format:\n/check Ali")
        return

    client = await db.fetchrow(
        "SELECT * FROM clients WHERE name=$1", name)

    if not client:
        await message.answer("❌ Mijoz topilmadi")
        return

    await message.answer(
        f"👤 {name}\n"
        f"💰 Qarz: {client['debt']}"
    )

# BARCHA QARZLAR
@dp.message(Command("list"))
async def list_clients(message: Message):

    clients = await db.fetch("SELECT * FROM clients")

    if not clients:
        await message.answer("📭 Qarzdor yo'q")
        return

    text = "📊 Qarzdorlar:\n\n"

    for c in clients:
        text += f"👤 {c['name']} — {c['debt']}\n"

    await message.answer(text)

# BOT ISHGA TUSHISH
async def main():
    await connect_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())