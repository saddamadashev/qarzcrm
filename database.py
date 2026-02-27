import os
import asyncpg

DATABASE_URL = os.getenv("DATABASE_URL")

pool = None

async def init_db():
    global pool
    pool = await asyncpg.create_pool(DATABASE_URL)

    async with pool.acquire() as conn:
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS clients(
            id SERIAL PRIMARY KEY,
            name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        await conn.execute("""
        CREATE TABLE IF NOT EXISTS debts(
            id SERIAL PRIMARY KEY,
            client_id INTEGER,
            amount FLOAT,
            type TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

async def add_client(name):
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO clients(name) VALUES($1)",
            name
        )

async def get_clients():
    async with pool.acquire() as conn:
        return await conn.fetch("SELECT * FROM clients")

async def add_debt(client_id, amount, type):
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO debts(client_id,amount,type) VALUES($1,$2,$3)",
            client_id, amount, type
        )

async def client_balance(client_id):
    async with pool.acquire() as conn:
        add = await conn.fetchval(
            "SELECT COALESCE(SUM(amount),0) FROM debts WHERE client_id=$1 AND type='add'",
            client_id
        )
        minus = await conn.fetchval(
            "SELECT COALESCE(SUM(amount),0) FROM debts WHERE client_id=$1 AND type='minus'",
            client_id
        )
        return add - minus