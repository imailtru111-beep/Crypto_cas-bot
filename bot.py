import asyncio
import logging
import os
from dotenv import load_dotenv

load_dotenv()

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from database.models import init_db
from payments.ton_watcher import payment_watcher
from handlers import main, roulette, mines, tower, payments, admin

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is required!")


async def main_func():
    # Init database
    await init_db()
    logger.info("Database initialized")

    # Create bot and dispatcher
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Register routers
    dp.include_router(admin.router)
    dp.include_router(main.router)
    dp.include_router(roulette.router)
    dp.include_router(mines.router)
    dp.include_router(tower.router)
    dp.include_router(payments.router)

    logger.info("Routers registered")

    # Start payment watcher in background
    asyncio.create_task(payment_watcher(bot))
    logger.info("Payment watcher started")

    # Start polling
    logger.info("Starting bot polling...")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main_func())
