import os
import asyncio
import asyncpg
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN topilmadi")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL topilmadi")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
pool = None

# ============ DATABASE INIT ============
async def init_db():
    global pool
    pool = await asyncpg.create_pool(DATABASE_URL)

    async with pool.acquire() as conn:
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS debts(
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            amount NUMERIC NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

# ============ ADMIN CHECK ============
def is_admin(user_id):
    return user_id == ADMIN_ID

# ============ MENU ============
menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="➕ Qarz qo‘shish")],
        [KeyboardButton(text="➖ To‘lov qilish")],
        [KeyboardButton(text="📊 Tekshirish")],
        [KeyboardButton(text="📢 Qarzdorlar")]
    ],
    resize_keyboard=True
)

user_state = {}

# ============ START ============
@dp.message(Command("start"))
async def start(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Ruxsat yo‘q")
        return

    await message.answer("Qarz CRM tizimi ishga tushdi 🚀", reply_markup=menu)

# ============ BUTTON HANDLERS ============
@dp.message(F.text == "➕ Qarz qo‘shish")
async def add_prompt(message: Message):
    if not is_admin(message.from_user.id):
        return
    user_state[message.from_user.id] = "add"
    await message.answer("Format:\nIsm Summa\nMasalan:\nAli 500000")

@dp.message(F.text == "➖ To‘lov qilish")
async def pay_prompt(message: Message):
    if not is_admin(message.from_user.id):
        return
    user_state[message.from_user.id] = "pay"
    await message.answer("Format:\nIsm Summa\nMasalan:\nAli 200000")

@dp.message(F.text == "📊 Tekshirish")
async def check_prompt(message: Message):
    if not is_admin(message.from_user.id):
        return
    user_state[message.from_user.id] = "check"
    await message.answer("Ismni kiriting")

@dp.message(F.text == "📢 Qarzdorlar")
async def list_debtors(message: Message):
    if not is_admin(message.from_user.id):
        return

    async with pool.acquire() as conn:
        rows = await conn.fetch("""
        SELECT name, SUM(amount) as total
        FROM debts
        GROUP BY name
        HAVING SUM(amount) > 0
        ORDER BY total DESC
        """)

    if not rows:
        await message.answer("Qarzdor yo‘q")
        return

    text = "📢 Qarzdorlar:\n\n"
    for row in rows:
        text += f"{row['name']} — {row['total']} so‘m\n"

    await message.answer(text)

# ============ TEXT HANDLER ============
@dp.message()
async def handle_input(message: Message):
    if not is_admin(message.from_user.id):
        return

    action = user_state.get(message.from_user.id)

    if not action:
        return

    text = message.text.strip()

    try:
        if action in ["add", "pay"]:
            parts = text.split()
            if len(parts) != 2:
                raise ValueError()

            name, amount = parts
            amount = float(amount)

            if action == "pay":
                amount = -abs(amount)

            async with pool.acquire() as conn:
                await conn.execute(
                    "INSERT INTO debts(name, amount) VALUES($1,$2)",
                    name, amount
                )

            await message.answer("✅ Amal muvaffaqiyatli bajarildi")

        elif action == "check":
            name = text

            async with pool.acquire() as conn:
                total = await conn.fetchval(
                    "SELECT COALESCE(SUM(amount),0) FROM debts WHERE name=$1",
                    name
                )

            await message.answer(f"{name} jami qarzi: {total} so‘m")

    except:
        await message.answer("❌ Format noto‘g‘ri")

    user_state[message.from_user.id] = None

# ============ MAIN ============
async def main():
    await init_db()
    print("CRM Bot started successfully 🚀")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())