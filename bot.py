import os
import asyncio
from aiogram import Bot, Dispatcher
from handlers import register_handlers
from database import init_db

BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

async def main():
    await init_db()
    register_handlers(dp)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())