import os
import asyncio
import asyncpg
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart
from aiogram.utils.keyboard import InlineKeyboardBuilder

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

db = None


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
        client_id INT,
        amount FLOAT,
        created_at TIMESTAMP
    )
    """)


async def get_clients():
    return await db.fetch("SELECT * FROM clients ORDER BY id")


async def get_balance(client_id):
    result = await db.fetchval(
        "SELECT COALESCE(SUM(amount),0) FROM debts WHERE client_id=$1",
        client_id
    )
    return result


async def clients_keyboard():
    builder = InlineKeyboardBuilder()

    clients = await get_clients()

    for c in clients:
        builder.button(text=c["name"], callback_data=f"client_{c['id']}")

    builder.button(text="➕ Mijoz qo‘shish", callback_data="add_client")
    builder.button(text="📊 Statistika", callback_data="stats")

    builder.adjust(1)
    return builder.as_markup()


async def client_menu(client_id):
    balance = await get_balance(client_id)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Qarz qo‘shish", callback_data=f"add_{client_id}")],
            [InlineKeyboardButton(text="➖ Qarz ayirish", callback_data=f"minus_{client_id}")],
            [InlineKeyboardButton(text=f"💰 Umumiy: {balance}", callback_data="none")],
            [InlineKeyboardButton(text="⬅️ Ortga", callback_data="back")]
        ]
    )

    return kb


@dp.message(CommandStart())
async def start(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Ruxsat yo‘q")
        return

    kb = await clients_keyboard()

    await message.answer(
        "📋 Qarzdorlar ro‘yxati",
        reply_markup=kb
    )


@dp.callback_query(lambda c: c.data == "back")
async def back(callback: types.CallbackQuery):
    kb = await clients_keyboard()
    await callback.message.edit_text("📋 Qarzdorlar", reply_markup=kb)


@dp.callback_query(lambda c: c.data == "add_client")
async def add_client(callback: types.CallbackQuery):
    await callback.message.answer("Mijoz ismini yozing:")


@dp.message()
async def add_client_name(message: Message):
    if message.text.startswith("/"):
        return

    name = message.text

    await db.execute(
        "INSERT INTO clients(name) VALUES($1)",
        name
    )

    kb = await clients_keyboard()

    await message.answer("✅ Mijoz qo‘shildi", reply_markup=kb)


@dp.callback_query(lambda c: c.data.startswith("client_"))
async def client_open(callback: types.CallbackQuery):
    client_id = int(callback.data.split("_")[1])

    kb = await client_menu(client_id)

    await callback.message.edit_text(
        "👤 Mijoz menyusi",
        reply_markup=kb
    )


@dp.callback_query(lambda c: c.data.startswith("add_"))
async def add_debt(callback: types.CallbackQuery):
    client_id = int(callback.data.split("_")[1])

    await callback.message.answer(
        f"{client_id} uchun qarz miqdorini yozing:"
    )

    dp.client_add = client_id


@dp.callback_query(lambda c: c.data.startswith("minus_"))
async def minus_debt(callback: types.CallbackQuery):
    client_id = int(callback.data.split("_")[1])

    await callback.message.answer(
        f"{client_id} uchun ayiriladigan summani yozing:"
    )

    dp.client_minus = client_id


@dp.message()
async def handle_amount(message: Message):

    try:
        amount = float(message.text)
    except:
        return

    if hasattr(dp, "client_add"):
        client_id = dp.client_add
        await db.execute(
            "INSERT INTO debts(client_id,amount,created_at) VALUES($1,$2,$3)",
            client_id,
            amount,
            datetime.now()
        )
        del dp.client_add

    elif hasattr(dp, "client_minus"):
        client_id = dp.client_minus
        await db.execute(
            "INSERT INTO debts(client_id,amount,created_at) VALUES($1,$2,$3)",
            client_id,
            -amount,
            datetime.now()
        )
        del dp.client_minus

    await message.answer("✅ Hisob yangilandi")


@dp.callback_query(lambda c: c.data == "stats")
async def stats(callback: types.CallbackQuery):

    total = await db.fetchval(
        "SELECT COALESCE(SUM(amount),0) FROM debts"
    )

    await callback.message.answer(
        f"📊 Umumiy qarz: {total}"
    )


async def main():
    await init_db()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())