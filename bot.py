import os
import asyncio
import asyncpg
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
pool = None


# ========== DB ==========
async def init_db():
    global pool
    pool = await asyncpg.create_pool(DATABASE_URL)

    async with pool.acquire() as conn:
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS debts(
            id SERIAL PRIMARY KEY,
            name TEXT,
            amount NUMERIC
        );
        """)


# ========== ADMIN ==========
def is_admin(user_id):
    return user_id == ADMIN_ID


# ========== MENU ==========
menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="➕ Qarz qo‘shish")],
        [KeyboardButton(text="➖ To‘lov qilish")],
        [KeyboardButton(text="📊 Tekshirish")],
        [KeyboardButton(text="📢 Qarzdorlar")]
    ],
    resize_keyboard=True
)

current_action = {}


# ========== START ==========
@dp.message(Command("start"))
async def start(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Ruxsat yo‘q")
        return

    await message.answer("Qarz CRM tizimi 🚀", reply_markup=menu)


# ========== BUTTONS ==========
@dp.message(F.text == "➕ Qarz qo‘shish")
async def add_prompt(message: Message):
    current_action[message.from_user.id] = "add"
    await message.answer("Format: Ism Summa\nMasalan:\nAli 500000")


@dp.message(F.text == "➖ To‘lov qilish")
async def pay_prompt(message: Message):
    current_action[message.from_user.id] = "pay"
    await message.answer("Format: Ism Summa\nMasalan:\nAli 200000")


@dp.message(F.text == "📊 Tekshirish")
async def check_prompt(message: Message):
    current_action[message.from_user.id] = "check"
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
        """)

    if not rows:
        await message.answer("Qarzdor yo‘q")
        return

    text = "📢 Qarzdorlar:\n\n"
    for row in rows:
        text += f"{row['name']} - {row['total']} so‘m\n"

    await message.answer(text)


# ========== TEXT HANDLER ==========
@dp.message()
async def handle_input(message: Message):
    if not is_admin(message.from_user.id):
        return

    action = current_action.get(message.from_user.id)

    if not action:
        return

    if action in ["add", "pay"]:
        try:
            name, amount = message.text.split()
            amount = float(amount)

            if action == "pay":
                amount = -amount

            async with pool.acquire() as conn:
                await conn.execute(
                    "INSERT INTO debts(name, amount) VALUES($1,$2)",
                    name, amount
                )

            await message.answer("✅ Amal bajarildi")
        except:
            await message.answer("Format xato")

    elif action == "check":
        name = message.text

        async with pool.acquire() as conn:
            total = await conn.fetchval(
                "SELECT COALESCE(SUM(amount),0) FROM debts WHERE name=$1",
                name
            )

        await message.answer(f"{name} jami qarzi: {total} so‘m")

    current_action[message.from_user.id] = None


# ========== MAIN ==========
async def main():
    await init_db()
    print("CRM Bot started...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
    