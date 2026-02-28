import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from config import TOKEN, SUPER_ADMIN_ID
from database import init_db, update_balance
import aiosqlite

bot = Bot(token=TOKEN)
dp = Dispatcher()

def main_kb(uid):
    kb = InlineKeyboardBuilder()
    kb.row(types.InlineKeyboardButton(text="👥 Mijozlar", callback_data="list"))
    kb.row(types.InlineKeyboardButton(text="➕ Yangi mijoz", callback_data="new"))
    kb.row(types.InlineKeyboardButton(text="📊 Statistika", callback_data="stats"))
    if uid == SUPER_ADMIN_ID:
        kb.row(types.InlineKeyboardButton(text="⚙️ Admin Panel", callback_data="admin"))
    return kb.as_markup()

@dp.message(CommandStart())
async def start(m: types.Message):
    await m.answer("🏦 **Qarz Daftari CRM**", reply_markup=main_kb(m.from_user.id))

# --- Mijozlar Ro'yxati ---
@dp.callback_query(F.data == "list")
async def list_cust(call: types.CallbackQuery):
    async with aiosqlite.connect("qarz_pro.db") as db:
        cursor = await db.execute("SELECT id, name, balance FROM customers WHERE owner_id=?", (call.from_user.id,))
        rows = await cursor.fetchall()
    
    kb = InlineKeyboardBuilder()
    for r in rows:
        kb.row(types.InlineKeyboardButton(text=f"{r[1]}: {r[2]:,.0f}", callback_data=f"view_{r[0]}"))
    kb.row(types.InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back"))
    await call.message.edit_text("Mijozni tanlang:", reply_markup=kb.as_markup())

# --- Statistika (Eng ko'p qarzlar) ---
@dp.callback_query(F.data == "stats")
async def stats(call: types.CallbackQuery):
    async with aiosqlite.connect("qarz_pro.db") as db:
        cursor = await db.execute("SELECT name, balance FROM customers WHERE owner_id=? ORDER BY balance DESC LIMIT 1", (call.from_user.id,))
        top = await cursor.fetchone()
    
    text = "📊 **Statistika**\n\n"
    if top:
        text += f"🔺 Eng ko'p qarz: {top[0]} ({top[1]:,.0f} so'm)"
    else:
        text += "Ma'lumot yo'q."
    await call.message.edit_text(text, reply_markup=main_kb(call.from_user.id))

@dp.callback_query(F.data == "back")
async def back(call: types.CallbackQuery):
    await call.message.edit_text("Asosiy menyu:", reply_markup=main_kb(call.from_user.id))

async def main():
    await init_db()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
