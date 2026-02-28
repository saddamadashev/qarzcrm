from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Mijoz qo‘shish", callback_data="add_customer")],
        [InlineKeyboardButton(text="📋 Mijozlar", callback_data="list_customers")],
        [InlineKeyboardButton(text="🏆 Reyting", callback_data="top")]
    ])