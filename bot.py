import os
import asyncio
import asyncpg
from datetime import datetime
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton
)
from aiogram.filters import Command

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

pool = None
user_state = {}
selected_client = {}

menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="➕ Mijoz qo'shish")],
        [KeyboardButton(text="📋 Mijozlar")],
        [KeyboardButton(text="💰 Umumiy qarz")],
        [KeyboardButton(text="📅 Oylik statistika")],
        [KeyboardButton(text="📈 Yillik statistika")]
    ],
    resize_keyboard=True
)

async def init_db():
    global pool
    pool = await asyncpg.create_pool(DATABASE_URL)

    async with pool.acquire() as conn:

        await conn.execute("""
        CREATE TABLE IF NOT EXISTS clients(
            id SERIAL PRIMARY KEY,
            name TEXT
        )
        """)

        await conn.execute("""
        CREATE TABLE IF NOT EXISTS transactions(
            id SERIAL PRIMARY KEY,
            client_id INTEGER,
            amount FLOAT,
            type TEXT,
            created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

def client_menu(client_id):

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Qarzni qo'shish", callback_data=f"add_{client_id}")],
            [InlineKeyboardButton(text="➖ Qarzni ayirish", callback_data=f"minus_{client_id}")],
            [InlineKeyboardButton(text="📊 Balans", callback_data=f"balance_{client_id}")],
            [InlineKeyboardButton(text="📜 Tarix", callback_data=f"history_{client_id}")]
        ]
    )

async def get_balance(client_id):

    async with pool.acquire() as conn:

        add = await conn.fetchval(
            "SELECT COALESCE(SUM(amount),0) FROM transactions WHERE client_id=$1 AND type='add'",
            client_id
        )

        minus = await conn.fetchval(
            "SELECT COALESCE(SUM(amount),0) FROM transactions WHERE client_id=$1 AND type='minus'",
            client_id
        )

        return add - minus

@dp.message(Command("start"))
async def start(message: Message):

    if message.from_user.id != ADMIN_ID:
        return

    await message.answer("Qarz CRM tizimi", reply_markup=menu)

@dp.message(F.text == "➕ Mijoz qo'shish")
async def add_client(message: Message):

    user_state[message.from_user.id] = "add_client"
    await message.answer("Mijoz ismini yozing")

@dp.message()
async def handle_input(message: Message):

    if message.from_user.id != ADMIN_ID:
        return

    state = user_state.get(message.from_user.id)

    if state == "add_client":

        name = message.text

        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO clients(name) VALUES($1)",
                name
            )

        user_state[message.from_user.id] = None

        await message.answer("Mijoz qo'shildi")

    elif state == "add_debt":

        client_id = selected_client[message.from_user.id]
        amount = float(message.text)

        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO transactions(client_id,amount,type) VALUES($1,$2,'add')",
                client_id, amount
            )

        user_state[message.from_user.id] = None
        await message.answer("Qarz qo'shildi")

    elif state == "minus_debt":

        client_id = selected_client[message.from_user.id]
        amount = float(message.text)

        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO transactions(client_id,amount,type) VALUES($1,$2,'minus')",
                client_id, amount
            )

        user_state[message.from_user.id] = None
        await message.answer("Qarz kamaytirildi")

@dp.message(F.text == "📋 Mijozlar")
async def clients(message: Message):

    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM clients")

    kb = InlineKeyboardMarkup(inline_keyboard=[])

    for r in rows:
        kb.inline_keyboard.append(
            [InlineKeyboardButton(text=r["name"], callback_data=f"client_{r['id']}")]
        )

    await message.answer("Mijozlar:", reply_markup=kb)

@dp.callback_query(F.data.startswith("client_"))
async def open_client(callback: CallbackQuery):

    client_id = int(callback.data.split("_")[1])
    await callback.message.edit_text("Mijoz menyusi", reply_markup=client_menu(client_id))

@dp.callback_query(F.data.startswith("add_"))
async def add_debt(callback: CallbackQuery):

    client_id = int(callback.data.split("_")[1])

    selected_client[callback.from_user.id] = client_id
    user_state[callback.from_user.id] = "add_debt"

    await callback.message.answer("Summani yozing")

@dp.callback_query(F.data.startswith("minus_"))
async def minus_debt(callback: CallbackQuery):

    client_id = int(callback.data.split("_")[1])

    selected_client[callback.from_user.id] = client_id
    user_state[callback.from_user.id] = "minus_debt"

    await callback.message.answer("To'lov summasini yozing")

@dp.callback_query(F.data.startswith("balance_"))
async def balance(callback: CallbackQuery):

    client_id = int(callback.data.split("_")[1])
    bal = await get_balance(client_id)

    await callback.answer(f"Balans: {bal} so'm", show_alert=True)

@dp.callback_query(F.data.startswith("history_"))
async def history(callback: CallbackQuery):

    client_id = int(callback.data.split("_")[1])

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM transactions WHERE client_id=$1 ORDER BY created DESC LIMIT 10",
            client_id
        )

    text = "So'nggi operatsiyalar:\n\n"

    for r in rows:
        sign = "+" if r["type"] == "add" else "-"
        date = r["created"].strftime("%d.%m.%Y %H:%M")
        text += f"{sign}{r['amount']} | {date}\n"

    await callback.message.answer(text)

@dp.message(F.text == "💰 Umumiy qarz")
async def total(message: Message):

    async with pool.acquire() as conn:

        add = await conn.fetchval("SELECT COALESCE(SUM(amount),0) FROM transactions WHERE type='add'")
        minus = await conn.fetchval("SELECT COALESCE(SUM(amount),0) FROM transactions WHERE type='minus'")

    await message.answer(f"Jami qarz: {add-minus}")

@dp.message(F.text == "📅 Oylik statistika")
async def month_stats(message: Message):

    async with pool.acquire() as conn:

        add = await conn.fetchval("""
        SELECT COALESCE(SUM(amount),0)
        FROM transactions
        WHERE type='add' AND DATE_TRUNC('month',created)=DATE_TRUNC('month',NOW())
        """)

        minus = await conn.fetchval("""
        SELECT COALESCE(SUM(amount),0)
        FROM transactions
        WHERE type='minus' AND DATE_TRUNC('month',created)=DATE_TRUNC('month',NOW())
        """)

    await message.answer(f"Oyda qo'shilgan: {add}\nTo'langan: {minus}")

@dp.message(F.text == "📈 Yillik statistika")
async def year_stats(message: Message):

    async with pool.acquire() as conn:

        add = await conn.fetchval("""
        SELECT COALESCE(SUM(amount),0)
        FROM transactions
        WHERE type='add' AND DATE_TRUNC('year',created)=DATE_TRUNC('year',NOW())
        """)

        minus = await conn.fetchval("""
        SELECT COALESCE(SUM(amount),0)
        FROM transactions
        WHERE type='minus' AND DATE_TRUNC('year',created)=DATE_TRUNC('year',NOW())
        """)

    await message.answer(f"Yilda qo'shilgan: {add}\nTo'langan: {minus}")

async def main():

    await init_db()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())