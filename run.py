import asyncio
import logging
from aiogram.fsm.storage.base import StorageKey
from arq import create_pool

from configuration.config_db import Base, engine
from configuration.config_bot import bot, dp, storage
from handlers.admin_send_scenarios import admin_send_script
from handlers.auth import auth_router

from handlers.doctor import doctor_router
from handlers.admin_general import admin_router
from handlers.admin_changes import admin_changes_router
from handlers.patient import patient_router
from aiogram.fsm.context import FSMContext

from scheduler.main import WorkerSettings
from database.models import *


async def on_startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def main():
    admin_router.include_router(admin_changes_router)
    admin_router.include_router(admin_send_script)
    auth_router.include_router(doctor_router)
    auth_router.include_router(patient_router)
    auth_router.include_router(admin_router)
    dp.include_router(auth_router)

    redis_pool = await create_pool(WorkerSettings.redis_settings)

    await bot.delete_webhook(drop_pending_updates=True)

    await on_startup()
    await dp.start_polling(bot, arqredis=redis_pool)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Exit")
