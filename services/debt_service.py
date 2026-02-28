from sqlalchemy import select, func
from models import Transaction

async def calculate_total_debt(session, client_id):
    result = await session.execute(
        select(func.sum(
            func.case(
                (Transaction.type == "add", Transaction.amount),
                else_=-Transaction.amount
            )
        )).where(Transaction.client_id == client_id)
    )
    total = result.scalar()
    return total or 0