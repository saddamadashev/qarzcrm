from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="➕ Mijoz qo'shish")],
        [KeyboardButton(text="📋 Mijozlar")],
        [KeyboardButton(text="📊 Umumiy qarz")],
        [KeyboardButton(text="📅 Oylik statistika")],
        [KeyboardButton(text="📈 Yillik statistika")]
    ],
    resize_keyboard=True
)

def client_keyboard(clients):
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for c in clients:
        kb.inline_keyboard.append(
            [InlineKeyboardButton(text=c["name"], callback_data=f"client_{c['id']}")]
        )
    return kb

def client_actions(client_id):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Qarzni qo'shish", callback_data=f"add_{client_id}")],
            [InlineKeyboardButton(text="➖ Qarzni ayirish", callback_data=f"minus_{client_id}")],
            [InlineKeyboardButton(text="📊 Umumiy qarz", callback_data=f"balance_{client_id}")],
        ]
    )