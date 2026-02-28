import os
import asyncio
from datetime import datetime

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, String, BigInteger, ForeignKey, DateTime, select, func, case

# ================= CONFIG =================

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))

DATABASE_URL = os.getenv("DATABASE_URL").replace(
    "postgresql://", "postgresql+asyncpg://"
)

# ================= DATABASE =================

engine = create_async_engine(DATABASE_URL, echo=False)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True)

class Client(Base):
    __tablename__ = "clients"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    full_name = Column(String)

class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey("clients.id"))
    amount = Column(Integer)
    type = Column(String)  # add / minus
    created_at = Column(DateTime, default=datetime.utcnow)

# ================= BOT =================

bot = Bot(BOT_TOKEN)
dp = Dispatcher()
state = {}

# ================= INIT =================

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_user(tg_id):
    async with SessionLocal() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == tg_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            user = User(telegram_id=tg_id)
            session.add(user)
            await session.commit()

        return user

async def calculate_total(client_id):
    async with SessionLocal() as session:
        result = await session.execute(
            select(
                func.sum(
                    case(
                        (Transaction.type == "add", Transaction.amount),
                        else_=-Transaction.amount
                    )
                )
            ).where(Transaction.client_id == client_id)
        )
        total = result.scalar()
        return total or 0

# ================= KEYBOARD =================

def main_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Mijoz qo‘shish")],
            [KeyboardButton(text="📋 Mijozlar")],
        ],
        resize_keyboard=True
    )

# ================= HANDLERS =================

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await get_user(message.from_user.id)
    await message.answer("Qarz CRM PRO ishga tushdi ✅", reply_markup=main_kb())

@dp.message(F.text == "➕ Mijoz qo‘shish")
async def add_client_start(message: types.Message):
    state[message.from_user.id] = "waiting_client"
    await message.answer("Mijoz ismini yuboring:")

@dp.message(F.text == "📋 Mijozlar")
async def list_clients(message: types.Message):
    async with SessionLocal() as session:
        user = await get_user(message.from_user.id)
        result = await session.execute(
            select(Client).where(Client.user_id == user.id)
        )
        clients = result.scalars().all()

    if not clients:
        await message.answer("Mijozlar yo‘q.")
        return

    text = "Mijozlar:\n"
    for c in clients:
        total = await calculate_total(c.id)
        text += f"\nID: {c.id}\n{c.full_name}\nQarz: {total}\n"

    await message.answer(text)

@dp.message()
async def universal_handler(message: types.Message):
    user_id = message.from_user.id

    if state.get(user_id) == "waiting_client":
        async with SessionLocal() as session:
            user = await get_user(user_id)
            client = Client(user_id=user.id, full_name=message.text)
            session.add(client)
            await session.commit()

        state[user_id] = None
        await message.answer("Mijoz qo‘shildi ✅", reply_markup=main_kb())
        return

    if message.text.startswith("+"):
        try:
            parts = message.text.split()
            client_id = int(parts[1])
            amount = int(parts[2])

            async with SessionLocal() as session:
                tr = Transaction(client_id=client_id, amount=amount, type="add")
                session.add(tr)
                await session.commit()

            total = await calculate_total(client_id)
            await message.answer(f"Qo‘shildi ✅\nYangi umumiy qarz: {total}")
        except:
            await message.answer("Format: + ID SUMMA")

    if message.text.startswith("-"):
        try:
            parts = message.text.split()
            client_id = int(parts[1])
            amount = int(parts[2])

            async with SessionLocal() as session:
                tr = Transaction(client_id=client_id, amount=amount, type="minus")
                session.add(tr)
                await session.commit()

            total = await calculate_total(client_id)
            await message.answer(f"Ayrildi ✅\nYangi umumiy qarz: {total}")
        except:
            await message.answer("Format: - ID SUMMA")

# ================= MAIN =================

async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())