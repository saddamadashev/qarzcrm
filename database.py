import aiosqlite
from datetime import datetime

async def init_db():
    async with aiosqlite.connect("qarz_daftar.db") as db:
        # Mijozlar jadvali
        await db.execute("""CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id INTEGER,
            name TEXT,
            balance REAL DEFAULT 0,
            last_update TEXT
        )""")
        # Tranzaksiyalar (Tarix va Chek uchun)
        await db.execute("""CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cust_id INTEGER,
            amount REAL,
            type TEXT,
            date TEXT
        )""")
        await db.commit()

async def add_transaction(cust_id, amount, t_type):
    async with aiosqlite.connect("qarz_daftar.db") as db:
        now = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        await db.execute("INSERT INTO transactions (cust_id, amount, type, date) VALUES (?,?,?,?)",
                         (cust_id, amount, t_type, now))
        if t_type == "PLUS":
            await db.execute("UPDATE customers SET balance = balance + ?, last_update = ? WHERE id = ?", (amount, now, cust_id))
        else:
            await db.execute("UPDATE customers SET balance = balance - ?, last_update = ? WHERE id = ?", (amount, now, cust_id))
        await db.commit()
