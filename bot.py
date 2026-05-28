import asyncio
import logging

from telegram.ext import Application, CommandHandler, MessageHandler, filters

from config import TELEGRAM_BOT_TOKEN
from db import init_db
from handlers import (
    handle_message,
    handle_start,
    handle_help_cmd,
    handle_testprompt,
    handle_testemail,
)
from scheduler import setup_scheduler

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

_scheduler = None


async def _post_init(application):
    global _scheduler
    _scheduler = setup_scheduler(application.bot)
    logger.info("Scheduler started — all jobs registered")


async def _post_shutdown(application):
    if _scheduler:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler shut down")


def main():
    init_db()
    logger.info("Database initialized")

    app = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .post_init(_post_init)
        .post_shutdown(_post_shutdown)
        .build()
    )

    app.add_handler(CommandHandler("start", handle_start))
    app.add_handler(CommandHandler("help", handle_help_cmd))
    app.add_handler(CommandHandler("testprompt", handle_testprompt))
    app.add_handler(CommandHandler("testemail", handle_testemail))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot starting...")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
