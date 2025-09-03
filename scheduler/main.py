import logging
import os
from typing import Callable, Awaitable, Any

from aiogram import Bot
from arq import cron
from arq.connections import RedisSettings

from scheduler.appointment_scheduler import check_new_appointments
from scheduler.appointment_scheduler import update_appointments
from scheduler.sched_tasks import send_scenario_message, check_and_send_4331_scenario, check_after_4331_procedure, \
    check_for_delete

logger = logging.getLogger(__name__)


async def startup(ctx):
    logger.info("Запуск воркера arq")
    ctx["bot"] = Bot(token=os.getenv("TOKEN"))


async def shutdown(ctx):
    logger.info("Завершение работы воркера arq")
    await ctx["bot"].session.close()


async def test_send_message(ctx, chat_id: int, text: str):
    bot: Bot = ctx["bot"]
    try:
        await bot.send_message(chat_id, text)
        logger.info(f"Сообщение '{text}' успешно отправлено в чат {chat_id}")
    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения в чат {chat_id}: {e}")


async def test_message_every_minute(ctx):
    logger.info("Выполнение cron-задания: test_message_every_minute")
    try:
        await test_send_message(ctx, 1153231214, "Запуск arq")
    except Exception as e:
        logger.error(e)


class WorkerSettings:
    redis_settings = RedisSettings(
        host=os.getenv("REDIS_HOST", "redis://redis:6379"),
        port=int(os.getenv("REDIS_PORT", 6379)),
        database=0,
    )

    functions: list[Callable[..., Awaitable[Any]]] = [
        check_new_appointments,
        send_scenario_message,
        update_appointments,
        check_and_send_4331_scenario,
        check_after_4331_procedure,
        check_for_delete,
    ]

    on_startup = startup
    on_shutdown = shutdown

    poll_delay = 1.0  # Интервал опроса в секундах
    max_jobs = 100  # Максимальное количество одновременно выполняемых задач
    job_timeout = 300  # Таймаут выполнения задачи в секундах
    keep_result = 3600  # Время хранения результата задачи в секундах
    cron_jobs = [
        cron(
            "scheduler.appointment_scheduler.check_new_appointments",
            minute={0, 30},
            second=0,
        ),
        cron(
            "scheduler.appointment_scheduler.update_appointments",
            minute={0, 30},
            second=0,
        ),
        cron(
            "scheduler.sched_tasks.check_for_delete",
            minute={0, 30},
            second=0,
        ),
    ]

    log_level = logging.INFO  # Уровень логирования
