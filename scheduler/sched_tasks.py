import asyncio
import logging
from datetime import datetime, timedelta

from aiogram import Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from sqlalchemy.future import select
from sqlalchemy.orm import joinedload

from configuration.config_bot import dp
from configuration.config_db import SessionLocal
from database.models import Appointment, Scenario, Client, UserScenario
from handlers.functions.auth_crm_fun import replace_content
from handlers.patient import switch_survey

send_lock = asyncio.Lock()


#
# logging.basicConfig(
#     level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
# )
#
#
# async def update_database_scheduler():
#     await set_sheduler()
#
#
# async def set_cleaning_database():
#     await clearing_supabase()
#


def split_message_to_two_parts(message, max_length):
    """
    Разделяет сообщение на две части, если его длина превышает максимальную.

    Сообщение делится на части, пытаясь найти подходящее место для разделения (после точки или пробела).
    Если не удается найти такие места, разделение происходит в середине строки.

    :param message: Текст сообщения, которое нужно разделить.
    :param max_length: Максимальная длина части сообщения.
    :return: Список из двух частей сообщения, если оно было разделено. Если длина сообщения меньше или равна
             максимальной, возвращается список с одним элементом (неразделенным сообщением).
    """
    if len(message) <= max_length:
        return [message]

    middle_index = len(message) // 2
    split_index = message.rfind(".", 0, middle_index)
    if split_index == -1:
        split_index = message.rfind(" ", 0, middle_index)
        if split_index == -1:
            split_index = middle_index

    part1 = message[: split_index + 1].strip()
    part2 = message[split_index + 1:].strip()

    return [part1, part2]


async def send_scenario_message(
        ctx, telegram_id, message_id, content, url, message_type, id_survey
):
    """
    Отправка очереди сообщений из redis.
    """
    async with send_lock:
        bot: Bot = ctx["bot"]

        state_with = FSMContext(
            storage=dp.storage,
            key=StorageKey(chat_id=telegram_id, user_id=telegram_id, bot_id=bot.id),
        )

        try:
            parts = split_message_to_two_parts(
                content, 4096 if message_type == "text" else 1024
            )

            if message_type == "text":
                for part in parts:
                    await bot.send_message(chat_id=telegram_id, text=part, parse_mode='HTML')
            elif message_type == "video":
                await bot.send_video(chat_id=telegram_id, video=url, caption=parts[0], parse_mode='HTML')
            elif message_type == "photo":
                await bot.send_photo(chat_id=telegram_id, photo=url, caption=parts[0], parse_mode='HTML')
            elif message_type == "audio":
                await bot.send_video(chat_id=telegram_id, video=url, caption=parts[0], parse_mode='HTML')
            elif message_type == "survey":
                await switch_survey(state_with, telegram_id, id_survey)
            else:
                logging.error(f"Unknown message type: {message_type}")

            if len(parts) > 1 and message_type == "text":
                await bot.send_message(chat_id=telegram_id, text=parts[1])

        except Exception as e:
            logging.error(
                f"Error while sending message {message_id} to {telegram_id}: {e}"
            )


async def schedule_scenario_message(
        ctx, telegram_id, message_id, send_time, content, url, message_type, id_survey
):
    """
    Загрузка очереди сообщений в redis из сценария

    :param telegram_id - тг-id пользователя
    :param message_id - id сообщения в сценарии
    :param send_time - время отправки
    :param content - содержимое сообщения (текст)
    :param url - ссылка/id контента
    :param message_type - тип сообщения
    :param id_survey - id опроса (если есть)
    """
    try:
        parts = split_message_to_two_parts(
            content, 4096 if message_type == "text" else 1024
        )
        first_part = parts.pop(0)

        # Добавляем задачу для отправки первой части сообщения
        await ctx["redis"].enqueue_job(
            "send_scenario_message",
            telegram_id=telegram_id,
            message_id=message_id,
            content=first_part,
            url=url,
            message_type=message_type,
            id_survey=id_survey,
            _defer_until=send_time + timedelta(seconds=(message_id + 1) * 2),
        )

        # Добавляем задачи для оставшихся частей
        if parts:
            send_time = send_time + timedelta(seconds=5)
            for part in parts:
                await ctx["redis"].enqueue_job(
                    "send_scenario_message",
                    telegram_id=telegram_id,
                    message_id=message_id,
                    content=part,
                    url="",
                    message_type="text",
                    id_survey=id_survey,
                    _defer_until=send_time,
                )
                send_time += timedelta(seconds=5)
    except Exception as e:
        logging.error(f"Error send message {message_id}: {e}")
        return


async def check_after_4331_procedure(ctx, tg_id, client_id, appointment_time):
    """
    Задаем провреку, что результат хгч положительный и он сменился на следующий этап в бд

    :param tg_id - тг-id клиента
    :param client_id - crm_id клиента
    :param appointment_time - время процедуры 4331 из бд
    """
    # Вычисляем время проверки через 8 дней
    check_time = appointment_time + timedelta(days=8)
    logging.info(f"schedule_check_for_procedure_4331 at {check_time}")
    # Добавляем задачу в планировщик
    await ctx["redis"].enqueue_job(
        "check_and_send_4331_scenario",
        tg_id=tg_id,
        client_id=client_id,
        _defer_until=check_time,
    )


async def check_and_send_4331_scenario(ctx, tg_id, client_id):
    """
    Проверяем, что процедура сдачи хгч сменилась на следующий сценарий (4331 сменились на 4332)
    """
    async with SessionLocal() as session:
        async with session.begin():
            try:
                stmt = select(Appointment).options(
                    joinedload(Appointment.client),
                    joinedload(Appointment.doctor),
                ).where(Appointment.client_id == client_id)

                result = await session.execute(stmt)
                appointment = result.scalar_one_or_none()

                if not appointment:
                    logging.warning(f"No appointment found for client_id {client_id}")
                    return

                procedure_to_check = {4332, 4333, 4334}
                if appointment.procedure_id in procedure_to_check:
                    scenario_stmt = select(Scenario).where(Scenario.stage == 6)
                    scenario_result = await session.execute(scenario_stmt)
                    scenarios = scenario_result.scalars().all()

                    client = appointment.client
                    doctor = appointment.doctor

                    client_first_name = client.first_name if client else ""
                    doctor_first_name = doctor.first_name if doctor else ""
                    doctor_last_name = doctor.last_name if doctor else ""

                    for scenario in scenarios:
                        updated_messages = [
                            await replace_content(
                                appointment.start_time,
                                message,
                                client_first_name,
                                doctor_first_name,
                                doctor_last_name,
                            )
                            for message in scenario.scenarios_msg.get("messages", [])
                        ]
                        scenario.scenarios_msg["messages"] = updated_messages

                        for message in updated_messages:
                            send_time = datetime.now() + timedelta(seconds=10)

                            await schedule_scenario_message(
                                ctx,
                                tg_id,
                                message["id"],
                                send_time,
                                message["content"],
                                message["url"],
                                message["type"],
                                None,
                            )
                    else:
                        logging.warning(f"No messages found for scenario 6")
            except Exception as e:
                logging.error(f"Error for check procedure 4331: {e}")


async def check_for_delete(ctx):
    """
    Ищет и удаляем пациентов и их записи, которые не обновлялись 30 дней
    """
    async with SessionLocal() as session:
        async with session.begin():
            try:
                months_ago = datetime.now() - timedelta(days=30)

                # Получение записей старше 30 дней
                stmt = select(Appointment).where(Appointment.start_time < months_ago).options(
                    joinedload(Appointment.client)
                )
                result = await session.execute(stmt)
                old_appointments = result.scalars().all()

                if not old_appointments:
                    logging.info("Записей для удаления не найдено")
                    return

                # Сбор client_id для удаления
                client_ids = {appointment.client_id for appointment in old_appointments if appointment.client_id}
                tg_ids_to_delete = []

                # Получение tg_id клиентов
                if client_ids:
                    stmt = select(Client).where(Client.id.in_(client_ids))
                    result = await session.execute(stmt)
                    clients = result.scalars().all()
                    tg_ids_to_delete = [client.tg_id for client in clients]

                # Удаление старых записей
                await session.execute(
                    Appointment.__table__.delete().where(Appointment.client_id.in_(client_ids))
                )

                # Удаление сценариев пользователей
                if tg_ids_to_delete:
                    await session.execute(
                        UserScenario.__table__.delete().where(UserScenario.clients_id.in_(tg_ids_to_delete))
                    )

                # Удаление клиентов
                await session.execute(
                    Client.__table__.delete().where(Client.id.in_(client_ids))
                )

                await session.commit()
                logging.info("Старые записи, клиенты и сценарии успешно удалены")

            except Exception as e:
                await session.rollback()
                logging.error(f"Ошибка при удалении старых записей: {e}")
