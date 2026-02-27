from database import pool

async def total_debt():
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "SELECT COALESCE(SUM(amount),0) FROM debts WHERE type='add'"
        )