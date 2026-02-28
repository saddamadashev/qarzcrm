import os
import asyncio
from datetime import datetime
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await bot.set_webhook(WEBHOOK_URL)
    yield
    await bot.delete_webhook()

app = FastAPI(lifespan=lifespan)

from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher
from aiogram.types import Update
from aiogram.filters import Command
from aiogram import types

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, String, BigInteger, ForeignKey, DateTime, select, func, case

# ================= CONFIG =================

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
BASE_URL = os.getenv("BASE_URL")  # Railway public url

raw_db = os.getenv("DATABASE_URL")
DATABASE_URL = raw_db.replace("postgresql://", "postgresql+asyncpg://")

WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"{BASE_URL}{WEBHOOK_PATH}"

# ================= DATABASE =================

engine = create_async_engine(DATABASE_URL, echo=False)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True)
    full_name = Column(String)
    role = Column(String, default="user")
    plan = Column(String, default="free")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Client(Base):
    __tablename__ = "clients"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    full_name = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey("clients.id"))
    amount = Column(Integer)
    type = Column(String)
    comment = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

# ================= BOT =================

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
app = FastAPI()

# ================= INIT =================

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

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

# ================= HANDLERS =================

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    user = await get_or_create_user(message.from_user)
    await message.answer("🚀 PRO SaaS Qarz CRM ishlayapti.")

# ================= WEBHOOK =================

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await bot.set_webhook(WEBHOOK_URL)
    yield
    await bot.delete_webhook()

app = FastAPI(lifespan=lifespan)

@app.post(WEBHOOK_PATH)
async def webhook(request: Request):
    update = Update.model_validate(await request.json())
    await dp.feed_update(bot, update)
    return {"ok": True}