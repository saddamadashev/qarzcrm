import os
import asyncio
from datetime import datetime

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, String, BigInteger, ForeignKey, DateTime, select, func, extract

# ================= CONFIG =================

BOT_TOKEN = os.getenv("8601271912:AAFou-qstt5iuagWP-p72edFTDgN6r3xg2c")
DATABASE_URL = os.getenv("postgresql://postgres:jpDjoyaxHiyQwdmvkVDicKJGSPZZJYkT@maglev.proxy.rlwy.net:34068/railway")
OWNER_ID = int(os.getenv("565876427"))

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

# ================= STATES =================

class AddClientState(StatesGroup):
    waiting_for_name = State()

class DebtState(StatesGroup):
    waiting_for_amount = State()
    waiting_for_comment = State()

# ================= HELPERS =================

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

async def calculate_total(session, client_id):
    result = await session.execute(
        select(func.sum(
            func.case(
                (Transaction.type == "add", Transaction.amount),
                else_=-Transaction.amount
            )
        )).where(Transaction.client_id == client_id)
    )
    total = result.scalar()
    return total or 0

# ================= START =================

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    user = await get_or_create_user(message.from_user)

    text = "🏦 QARZ CRM BOT\n\n"
    text += "➕ /addclient - Mijoz qo‘shish\n"
    text += "📋 /clients - Mijozlar\n"

    if user.role == "owner":
        text += "\n👑 /admin - Admin panel"

    await message.answer(text)

# ================= ADD CLIENT =================

@dp.message(Command("addclient"))
async def add_client_start(message: types.Message, state: FSMContext):
    await state.set_state(AddClientState.waiting_for_name)
    await message.answer("👤 Mijoz ismini kiriting:")

@dp.message(AddClientState.waiting_for_name)
async def save_client(message: types.Message, state: FSMContext):
    user = await get_or_create_user(message.from_user)

    async with SessionLocal() as session:
        count = await session.scalar(
            select(func.count(Client.id)).where(Client.user_id == user.id)
        )

        if user.plan == "free" and count >= 5:
            await message.answer("⚠️ Free limit 5 ta mijoz.")
            await state.clear()
            return

        client = Client(user_id=user.id, full_name=message.text)
        session.add(client)
        await session.commit()

    await message.answer("✅ Mijoz qo‘shildi.")
    await state.clear()

# ================= LIST CLIENTS =================

@dp.message(Command("clients"))
async def list_clients(message: types.Message):
    user = await get_or_create_user(message.from_user)

    async with SessionLocal() as session:
        result = await session.execute(
            select(Client).where(Client.user_id == user.id)
        )
        clients = result.scalars().all()

    if not clients:
        await message.answer("❌ Mijoz yo‘q.")
        return

    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text=c.full_name, callback_data=f"client_{c.id}")]
            for c in clients
        ]
    )

    await message.answer("📋 Mijozni tanlang:", reply_markup=keyboard)

# ================= CLIENT MENU =================

@dp.callback_query(F.data.startswith("client_"))
async def client_menu(callback: types.CallbackQuery):
    client_id = int(callback.data.split("_")[1])

    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="➕ Qarz qo‘shish", callback_data=f"add_{client_id}")],
            [types.InlineKeyboardButton(text="➖ Qarz ayirish", callback_data=f"sub_{client_id}")],
            [types.InlineKeyboardButton(text="📜 Tarix", callback_data=f"history_{client_id}")],
            [types.InlineKeyboardButton(text="📊 Oylik hisobot", callback_data=f"report_{client_id}")]
        ]
    )

    await callback.message.edit_text("👤 Mijoz menyusi:", reply_markup=keyboard)

# ================= ADD / SUBTRACT =================

@dp.callback_query(F.data.startswith("add_") | F.data.startswith("sub_"))
async def start_debt(callback: types.CallbackQuery, state: FSMContext):
    data = callback.data.split("_")
    tx_type = "add" if data[0] == "add" else "subtract"
    client_id = int(data[1])

    await state.update_data(type=tx_type, client_id=client_id)
    await state.set_state(DebtState.waiting_for_amount)
    await callback.message.answer("💰 Summani kiriting:")

@dp.message(DebtState.waiting_for_amount)
async def get_amount(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❌ Faqat son.")
        return

    await state.update_data(amount=int(message.text))
    await state.set_state(DebtState.waiting_for_comment)
    await message.answer("📝 Izoh kiriting:")

@dp.message(DebtState.waiting_for_comment)
async def save_transaction(message: types.Message, state: FSMContext):
    data = await state.get_data()
    user = await get_or_create_user(message.from_user)

    async with SessionLocal() as session:
        tx_count = await session.scalar(select(func.count(Transaction.id)))

        if user.plan == "free" and tx_count >= 300:
            await message.answer("⚠️ Free limit tugadi.")
            await state.clear()
            return

        tx = Transaction(
            client_id=data["client_id"],
            amount=data["amount"],
            type=data["type"],
            comment=message.text
        )
        session.add(tx)
        await session.commit()

        total = await calculate_total(session, data["client_id"])

    symbol = "➕" if data["type"] == "add" else "➖"

    await message.answer(f"""
━━━━━━━━━━━━━━
🧾 QARZ CHEKI
━━━━━━━━━━━━━━
{symbol} {data["amount"]:,} so‘m
📝 {message.text}

💳 Umumiy qarz:
{total:,} so‘m
━━━━━━━━━━━━━━
""")

    await state.clear()

# ================= HISTORY =================

@dp.callback_query(F.data.startswith("history_"))
async def show_history(callback: types.CallbackQuery):
    client_id = int(callback.data.split("_")[1])

    async with SessionLocal() as session:
        result = await session.execute(
            select(Transaction)
            .where(Transaction.client_id == client_id)
            .order_by(Transaction.created_at.desc())
            .limit(10)
        )
        transactions = result.scalars().all()

    if not transactions:
        await callback.message.answer("📭 Tarix yo‘q.")
        return

    text = "📜 Oxirgi 10 operatsiya:\n\n"
    for t in transactions:
        symbol = "➕" if t.type == "add" else "➖"
        text += f"{symbol} {t.amount:,} | {t.created_at.date()}\n"

    await callback.message.answer(text)

# ================= MONTHLY REPORT =================

@dp.callback_query(F.data.startswith("report_"))
async def monthly_report(callback: types.CallbackQuery):
    client_id = int(callback.data.split("_")[1])
    now = datetime.now()

    async with SessionLocal() as session:
        added = await session.scalar(
            select(func.sum(Transaction.amount)).where(
                Transaction.client_id == client_id,
                Transaction.type == "add",
                extract("month", Transaction.created_at) == now.month
            )
        )
        subtracted = await session.scalar(
            select(func.sum(Transaction.amount)).where(
                Transaction.client_id == client_id,
                Transaction.type == "subtract",
                extract("month", Transaction.created_at) == now.month
            )
        )

    added = added or 0
    subtracted = subtracted or 0

    await callback.message.answer(f"""
📊 Oylik hisobot

➕ Qo‘shilgan: {added:,}
➖ Ayirilgan: {subtracted:,}
💳 Sof: {(added - subtracted):,}
""")

# ================= ADMIN =================

@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    user = await get_or_create_user(message.from_user)
    if user.role != "owner":
        return

    async with SessionLocal() as session:
        total_users = await session.scalar(select(func.count(User.id)))
        total_clients = await session.scalar(select(func.count(Client.id)))
        total_tx = await session.scalar(select(func.count(Transaction.id)))

    await message.answer(f"""
👑 ADMIN PANEL

👥 Userlar: {total_users}
📋 Mijozlar: {total_clients}
💸 Tranzaksiya: {total_tx}
""")

# ================= MAIN =================

async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())