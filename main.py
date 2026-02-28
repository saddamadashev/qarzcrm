import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from sqlalchemy import select, func

from config import BOT_TOKEN, OWNER_ID
from database import SessionLocal, engine, Base
from models import User, Client, Transaction

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ---------------- INIT DATABASE ----------------

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# ---------------- GET OR CREATE USER ----------------

async def get_or_create_user(tg_user):
    async with SessionLocal() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == tg_user.id)
        )
        user = result.scalar_one_or_none()

        if not user:
            role = "owner" if tg_user.id == OWNER_ID else "user"
            user = User(
                telegram_id=tg_user.id,
                full_name=tg_user.full_name,
                role=role
            )
            session.add(user)
            await session.commit()

        return user

# ---------------- START ----------------

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    user = await get_or_create_user(message.from_user)

    text = "🏠 Qarz CRM Bot\n\n"
    text += "➕ Mijoz qo‘shish\n"
    text += "📋 Mijozlarim\n"
    text += "📊 Hisobot\n"

    if user.role == "owner":
        text += "\n👑 Admin Panel mavjud"

    await message.answer(text)

# ---------------- ADD CLIENT ----------------

@dp.message(Command("addclient"))
async def add_client(message: types.Message):
    user = await get_or_create_user(message.from_user)

    async with SessionLocal() as session:
        result = await session.execute(
            select(func.count(Client.id)).where(Client.user_id == user.id)
        )
        count = result.scalar()

        if user.plan == "free" and count >= 5:
            await message.answer("⚠️ Free limit tugadi. Premiumga o‘ting.")
            return

        client = Client(
            user_id=user.id,
            full_name="Test Client"
        )
        session.add(client)
        await session.commit()

    await message.answer("✅ Mijoz qo‘shildi")

# ---------------- ADMIN PANEL ----------------

@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    user = await get_or_create_user(message.from_user)

    if user.role != "owner":
        return

    async with SessionLocal() as session:
        total_users = await session.scalar(select(func.count(User.id)))
        total_clients = await session.scalar(select(func.count(Client.id)))
        total_transactions = await session.scalar(select(func.count(Transaction.id)))

    text = f"""
👑 ADMIN PANEL

👥 Userlar: {total_users}
📋 Mijozlar: {total_clients}
💸 Tranzaksiyalar: {total_transactions}
"""

    await message.answer(text)

# ---------------- MAIN ----------------

async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())