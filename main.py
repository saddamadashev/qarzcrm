import telebot
from telebot import types
import sqlite3
from datetime import datetime
import time
import os
import psycopg2
import psycopg2
import os

# Railway avtomatik beradigan ulanish manzili
DB_URL = os.environ.get('DATABASE_URL')

def get_db_connection():
    # SSL rejimini 'require' qilish Railway uchun shart
    conn = psycopg2.connect(DB_URL, sslmode='require')
    return conn

# Railway bergan ulanish manzilini olish
DATABASE_URL = os.environ.get('DATABASE_URL')

def get_connection():
    return psycopg2.connect(DATABASE_URL, sslmode='require')


# --- SOZLAMALAR ---
TOKEN = '8736208200:AAFge15TkEDq-VF8y77NUQcMc5HIpIK30g0'
bot = telebot.TeleBot(TOKEN)

# Bazani ulash va yaratish
def db_query(query, params=(), fetch=False):
    conn = sqlite3.connect('qarzdorlar_final.db')
    cursor = conn.cursor()
    cursor.execute(query, params)
    res = cursor.fetchall() if fetch else None
    conn.commit()
    conn.close()
    return res

# Jadvallarni tekshirish
db_query('''CREATE TABLE IF NOT EXISTS mijozlar 
            (id INTEGER PRIMARY KEY AUTOINCREMENT, ism TEXT, qarz REAL, sana TEXT)''')

# --- YORDAMCHI FUNKSIYALAR ---
def f_m(n):
    """Pullarni chiroyli formatlash: 1 000 000 so'm"""
    return "{:,.0f}".format(n or 0).replace(",", " ")

def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("➕ Yangi mijoz", "👥 Mijozlar ro'yxati")
    markup.add("📊 Statistika", "🏆 Reyting")
    return markup

# --- ASOSIY HANDLERLAR ---
@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "💰 **Asosiy menyuga xush kelibsiz!**", 
                     reply_markup=main_menu(), parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "➕ Yangi mijoz")
def add_start(message):
    msg = bot.send_message(message.chat.id, "👤 Yangi mijoz ismini kiriting:")
    bot.register_next_step_handler(msg, save_client)

def save_client(message):
    if message.text in ["/start", "⬅️ Orqaga"]: return start(message)
    db_query("INSERT INTO mijozlar (ism, qarz, sana) VALUES (?, 0, ?)", 
             (message.text, datetime.now().strftime("%Y-%m-%d %H:%M")))
    bot.send_message(message.chat.id, f"✅ **{message.text}** muvaffaqiyatli qo'shildi!", reply_markup=main_menu(), parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "👥 Mijozlar ro'yxati")
def list_clients(message):
    show_list(message.chat.id)

def show_list(chat_id, message_id=None):
    rows = db_query("SELECT id, ism, qarz FROM mijozlar", fetch=True)
    # Umumiy qarzlarni jamlash
    total_res = db_query("SELECT SUM(qarz) FROM mijozlar", fetch=True)[0][0]
    total_sum = total_res if total_res else 0
    
    kb = types.InlineKeyboardMarkup(row_width=1)
    for r in rows:
        kb.add(types.InlineKeyboardButton(f"{r[1]} | {f_m(r[2])} so'm", callback_data=f"view_{r[0]}"))
    
    text = f"👥 **Mijozlar ro'yxati**\n━━━━━━━━━━━━━━━\n💰 Jami qarzlar summasi:\n👉 **{f_m(total_sum)}** so'm\n━━━━━━━━━━━━━━━\n\nBatafsil ko'rish uchun tanlang:"
    
    try:
        if message_id:
            bot.edit_message_text(text, chat_id, message_id, reply_markup=kb, parse_mode="Markdown")
        else:
            bot.send_message(chat_id, text, reply_markup=kb, parse_mode="Markdown")
    except: pass

# --- CALLBACK LOGIKASI ---
@bot.callback_query_handler(func=lambda call: True)
def callback_logic(call):
    data = call.data.split("_")
    action = data[0]
    mid = data[1] if len(data) > 1 else None

    if action == "view":
        c = db_query("SELECT * FROM mijozlar WHERE id=?", (mid,), fetch=True)[0]
        # Muddatni hisoblash
        sana_obj = datetime.strptime(c[3], "%Y-%m-%d %H:%M")
        kunlar = (datetime.now() - sana_obj).days
        holat = "⚠️ MUDDATI O'TGAN" if kunlar >= 30 and c[2] > 0 else "✅ Joyida"

        text = (f"👤 **Mijoz:** {c[1]}\n"
                f"💰 **Qarzi:** {f_m(c[2])} so'm\n"
                f"📅 **Oxirgi o'zgarish:** {c[3]}\n"
                f"⏳ **Holat:** {holat} ({kunlar} kun)\n"
                f"━━━━━━━━━━━━━━━")
        
        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.add(types.InlineKeyboardButton("➕ Qarz qo'shish", callback_data=f"plus_{mid}"),
               types.InlineKeyboardButton("➖ Qarz ayirish", callback_data=f"minus_{mid}"))
        kb.add(types.InlineKeyboardButton("🗑 O'chirish", callback_data=f"conf_{mid}"))
        kb.add(types.InlineKeyboardButton("⬅️ Orqaga qaytish", callback_data="back_list"))
        
        try:
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="Markdown")
        except: pass

    elif action == "back":
        show_list(call.message.chat.id, call.message.message_id)

    elif action == "plus" or action == "minus":
        # Eski xabarni o'chiramizki, yangi summa so'rash xabari adashtirmasin
        bot.delete_message(call.message.chat.id, call.message.message_id)
        msg = bot.send_message(call.message.chat.id, f"💰 Summani kiriting (Faqat raqam):")
        bot.register_next_step_handler(msg, lambda m: update_debt(m, mid, action))

    elif action == "conf":
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("✅ HA, o'chirilsin", callback_data=f"del_{mid}"))
        kb.add(types.InlineKeyboardButton("❌ YO'Q, qolsin", callback_data=f"view_{mid}"))
        bot.edit_message_text("⚠️ Ushbu mijozni o'chirmoqchimisiz?", call.message.chat.id, call.message.message_id, reply_markup=kb)

    elif action == "del":
        db_query("DELETE FROM mijozlar WHERE id=?", (mid,))
        bot.answer_callback_query(call.id, "Mijoz o'chirildi")
        show_list(call.message.chat.id, call.message.message_id)

def update_debt(message, mid, action):
    try:
        val = float(message.text.replace(" ", ""))
        if action == "minus": val = -val
        db_query("UPDATE mijozlar SET qarz = qarz + ?, sana = ? WHERE id = ?", 
                 (val, datetime.now().strftime("%Y-%m-%d %H:%M"), mid))
        bot.send_message(message.chat.id, "✅ Muvaffaqiyatli saqlandi!")
        show_list(message.chat.id)
    except:
        bot.send_message(message.chat.id, "❌ Xato! Faqat raqam kiriting (Masalan: 500000)")

@bot.message_handler(func=lambda m: m.text == "📊 Statistika")
def statistics(message):
    data = db_query("SELECT COUNT(*), SUM(qarz) FROM mijozlar", fetch=True)[0]
    total_clients = data[0]
    total_sum = data[1] or 0
    text = (f"📊 **UMUMIY STATISTIKA**\n━━━━━━━━━━━━━━━\n"
            f"👥 Jami mijozlar: **{total_clients} ta**\n"
            f"💰 Umumiy qarzlar: **{f_m(total_sum)}** so'm\n"
            f"📅 Bugungi sana: {datetime.now().strftime('%Y-%m-%d')}\n━━━━━━━━━━━━━━━")
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "🏆 Reyting")
def rating(message):
    rows = db_query("SELECT ism, qarz FROM mijozlar WHERE qarz > 0 ORDER BY qarz DESC LIMIT 5", fetch=True)
    if not rows: return bot.send_message(message.chat.id, "Hozircha qarzdorlar yo'q.")
    res = "🏆 **ENG KO'P QARZDORLAR**\n\n"
    for i, r in enumerate(rows, 1):
        res += f"{i}. {r[0]} — **{f_m(r[1])}** so'm\n"
    bot.send_message(message.chat.id, res, parse_mode="Markdown")

# --- CARNETS UCHUN ISHGA TUSHIRISH ---
if __name__ == "__main__":
    print("🚀 Bot Carnets-da ishga tushdi...")
    while True:
        try:
            # Har safar ulanishdan oldin eski xabarlarni tozalaydi
            bot.delete_webhook(drop_pending_updates=True)
            
            # Polling vaqtini uzaytiramiz (iPhone uchun optimal)
            bot.infinity_polling(timeout=90, long_polling_timeout=20)
            
        except Exception as e:
            # Xato bo'lsa, logga yozadi va 5 soniyadan keyin qayta urinadi
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Xato: {e}")
            time.sleep(5)
            continue
