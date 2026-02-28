from datetime import datetime

def format_money(amount):
    return f"{int(amount):,}".replace(",", " ") + " so'm"

def create_receipt(name, amount, t_type, balance):
    now = datetime.now().strftime("%d.%m.%Y | %H:%M")
    sign = "➕" if t_type == "PLUS" else "➖"

    return (
        "🧾 <b>TO'LOV CHEKI</b>\n"
        "------------------------\n"
        f"👤 Mijoz: {name}\n"
        f"🕒 Sana: {now}\n"
        f"{sign} {format_money(amount)}\n"
        "------------------------\n"
        f"📊 Yangi balans: {format_money(balance)}"
    )