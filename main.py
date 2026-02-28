import asyncio
from datetime import datetime
import aiosqlite

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext

from config import BOT_TOKEN
from database import init_db, DB_NAME
from keyboards import main_menu
from states import AddCustomer
from utils import format_money

dp = Dispatcher()

# START
@dp.message(CommandStart())
async def start(message: types.Message):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users VALUES (?, ?)",
            (message.from_user.id, datetime.now().isoformat())
        )
        await db.commit()

    await message.answer("🏦 Qarz CRM 2.0", reply_markup=main_menu())


# ADD CUSTOMER
@dp.callback_query(F.data == "add_customer")
async def add_customer(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer("Mijoz ismini kiriting:")
    await state.set_state(AddCustomer.waiting_name)


@dp.message(AddCustomer.waiting_name)
async def save_customer(message: types.Message, state: FSMContext):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT INTO customers (owner_id, name, created_at) VALUES (?, ?, ?)",
            (message.from_user.id, message.text, datetime.now().isoformat())
        )
        await db.commit()

    await message.answer("✅ Mijoz qo‘shildi.", reply_markup=main_menu())
    await state.clear()


# LIST CUSTOMERS
@dp.callback_query(F.data == "list_customers")
async def list_customers(call: types.CallbackQuery):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "SELECT name FROM customers WHERE owner_id=?",
            (call.from_user.id,)
        )
        rows = await cursor.fetchall()

    if not rows:
        text = "Mijozlar yo‘q."
    else:
        text = "📋 Mijozlar:\n\n"
        for row in rows:
            text += f"• {row[0]}\n"

    await call.message.edit_text(text, reply_markup=main_menu())


async def main():
    await init_db()
    bot = Bot(token=BOT_TOKEN)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
