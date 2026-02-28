import asyncio
import logging
from datetime import datetime, timedelta
import aiosqlite
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

# --- SOZLAMALAR ---
import os
TOKEN = os.getenv("BOT_TOKEN")
SUPER_ADMIN_ID = 565876427

logging.basicConfig(level=logging.INFO)

# --- HOLATLAR (FSM) ---
class DebtFlow(StatesGroup):
    choosing_customer = State()
    entering_amount = State()
    setting_deadline = State()

# --- BAZA BILAN ISHLASH ---
async def init_db():
    async with aiosqlite.connect("finance_pro.db") as db:
        # Foydalanuvchilar (Do'kon egalari)
        await db.execute("""CREATE TABLE IF NOT EXISTS users 
            (user_id INTEGER PRIMARY KEY, joined_at TEXT)""")
        # Mijozlar
        await db.execute("""CREATE TABLE IF NOT EXISTS customers 
            (id INTEGER PRIMARY KEY AUTOINCREMENT, owner_id INTEGER, name TEXT, 
             balance REAL DEFAULT 0, deadline TEXT)""")
        # Tranzaksiyalar (Tarix va Chek uchun)
        await db.execute("""CREATE TABLE IF NOT EXISTS history 
            (id INTEGER PRIMARY KEY AUTOINCREMENT, cust_id INTEGER, amount REAL, 
             type TEXT, timestamp TEXT)""")
        await db.commit()

# --- QULAYLIKLAR (Chek va Formatlash) ---
def format_money(amount):
    return f"{amount:,.0f}".replace(",", " ") + " so'm"

def create_receipt(c_name, amount, t_type, new_balance):
    now = datetime.now().strftime("%d.%m.%Y | %H:%M")
    sign = "➕" if t_type == "PLUS" else "➖"
    return (
        f"🧾 **TO'LOV CHEKI**\n"
        f"----------------------------\n"
        f"👤 Mijoz: {c_name}\n"
        f"🕒 Sana: {now}\n"
        f"💰 Amaliyot: {sign} {format_money(amount)}\n"
        f"----------------------------\n"
        f"📉 Umumiy qarz: {format_money(new_balance)}\n"
        f"✅ Muvaffaqiyatli bajarildi."
    )

# --- ASOSIY MENYU ---
def main_menu(user_id):
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="👥 Mijozlar", callback_data="list_cust"))
    builder.row(types.InlineKeyboardButton(text="📊 Statistika", callback_data="stats"))
    builder.row(types.InlineKeyboardButton(text="🔔 Muddati kelganlar", callback_data="reminders"))
    if user_id == SUPER_ADMIN_ID:
        builder.row(types.InlineKeyboardButton(text="⚙️ Admin Paneli", callback_data="admin_panel"))
    # Yangi funksiyalar uchun joy (Kelajakda bitta tugma bilan qo'shish uchun)
    builder.row(types.InlineKeyboardButton(text="🚀 Yangi xizmatlar", callback_data="new_features"))
    return builder.as_markup()

# --- HANDLERLAR ---
dp = Dispatcher()

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    async with aiosqlite.connect("finance_pro.db") as db:
        await db.execute("INSERT OR IGNORE INTO users VALUES (?, ?)", 
                         (message.from_user.id, datetime.now().isoformat()))
        await db.commit()
    await message.answer("🏦 **Qarz Boshqaruv Tizimi**\nKerakli bo'limni tanlang:", 
                         reply_markup=main_menu(message.from_user.id))

# Statistika Funksiyasi
@dp.callback_query(F.data == "stats")
async def show_stats(call: types.CallbackQuery):
    async with aiosqlite.connect("finance_pro.db") as db:
        # Eng ko'p qarz
        cursor = await db.execute("SELECT name, balance FROM customers WHERE owner_id=? ORDER BY balance DESC LIMIT 1", (call.from_user.id,))
        top_debtor = await cursor.fetchone()
        
        # Jami aylanma
        cursor = await db.execute("SELECT SUM(balance) FROM customers WHERE owner_id=?", (call.from_user.id,))
        total = await cursor.fetchone()

    text = "📊 **SHAXSIY STATISTIKA**\n\n"
    if top_debtor:
        text += f"🔺 Eng ko'p qarz: {top_debtor[0]} ({format_money(top_debtor[1])})\n"
    text += f"💰 Umumiy qarzlar yig'indisi: {format_money(total[0] or 0)}"
    
    await call.message.edit_text(text, reply_markup=main_menu(call.from_user.id))

# Yangi funksiyalar (Zaxira joyi)
@dp.callback_query(F.data == "new_features")
async def new_features(call: types.CallbackQuery):
    await call.answer("Tez kunda: Excel hisobot, Telegram orqali xabarnoma yuborish va h.k.", show_alert=True)

# --- ISHGA TUSHIRISH ---
async def main():
    await init_db()
    bot = Bot(token=TOKEN)
    print("Bot muvaffaqiyatli yoqildi!")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
