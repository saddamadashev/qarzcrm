from aiogram import types, F
from aiogram.filters import Command
from keyboards import main_menu, client_keyboard, client_actions
from database import add_client, get_clients, add_debt, client_balance

ADMIN_ID = 123456789

def register_handlers(dp):

    @dp.message(Command("start"))
    async def start(message: types.Message):
        if message.from_user.id != ADMIN_ID:
            return
        await message.answer("Qarz CRM bot", reply_markup=main_menu)

    @dp.message(F.text == "➕ Mijoz qo'shish")
    async def add_client_start(message: types.Message):
        await message.answer("Mijoz ismini yozing")

    @dp.message()
    async def save_client(message: types.Message):
        await add_client(message.text)
        await message.answer("Mijoz qo'shildi")

    @dp.message(F.text == "📋 Mijozlar")
    async def show_clients(message: types.Message):
        clients = await get_clients()
        await message.answer("Mijozlar:", reply_markup=client_keyboard(clients))

    @dp.callback_query(F.data.startswith("client_"))
    async def client_menu(callback: types.CallbackQuery):
        client_id = int(callback.data.split("_")[1])
        await callback.message.edit_text(
            "Mijoz menyusi",
            reply_markup=client_actions(client_id)
        )

    @dp.callback_query(F.data.startswith("balance_"))
    async def balance(callback: types.CallbackQuery):
        client_id = int(callback.data.split("_")[1])
        bal = await client_balance(client_id)
        await callback.answer(f"Qarz: {bal}", show_alert=True)