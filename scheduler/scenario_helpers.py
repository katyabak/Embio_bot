from sqlalchemy.future import select

from configuration.config_db import SessionLocal
from database.constants_db import logger
from database.models import Client, UserScenario, Appointment


async def list_clients():
    """
    Получение всего списка клиентов из бд
    """
    async with SessionLocal() as session:
        async with session.begin():
            try:
                stmt = select(Client)
                result = await session.execute(stmt)
                clients = result.scalars().all()

                client_schedules = []
                for client in clients:
                    crm_id = client.id_crm
                    tg_id = client.tg_id

                    client_schedule = {"crm_id": crm_id, "tg_id": tg_id}

                    client_schedules.append(client_schedule)

                logger.info(f"Составлен список клиентов: {client_schedules}")
                return client_schedules

            except Exception as e:
                logger.exception(f"Ошибка при получении нового расписание из crm: {e}")


async def get_users_scenarios(tg_id):
    """
    Получение сценария пациента по его телеграмм-id

    :param tg_id - телеграмм id пациента
    :return - информация о сценарии (его id, сценарий, этап и т.п.)
    """
    async with SessionLocal() as session:
        async with session.begin():
            try:
                stmt = select(UserScenario).where(UserScenario.clients_id == tg_id)
                result = await session.execute(stmt)
                user_scenario = result.scalar()

                if not user_scenario:
                    return None

                items = {
                    "scenario_id": user_scenario.id,
                    "messages": user_scenario.scenarios.get("messages", []),
                    "name_stage": user_scenario.scenarios.get("name_stage", ""),
                    "procedures": user_scenario.scenarios.get("procedures", []),
                }

                return items

            except Exception as e:
                logger.exception(f"Ошибка при личный сценариев на отправку: {e}")
                return None


async def get_telegram_id(client_id):
    async with SessionLocal() as session:
        async with session.begin():
            try:
                stmt = select(Client).where(Client.id == client_id)
                result = await session.execute(stmt)
                client = result.scalars().first()

                if not client:
                    return None

                items = {"tg_id": client.tg_id}
                logger.exception(f"Пользователь с id найден: {client.tg_id}")

                return items

            except Exception as e:
                logger.exception(
                    f"Ошибка получения tg_id клиента для отправки сообщений: {e}"
                )
                return None


async def get_new_appointments():
    """
    Проверка на наличие сценариев, которые необходимо отправить в бд
    """
    async with SessionLocal() as session:
        async with session.begin():
            try:
                stmt = select(Appointment).where(Appointment.processed == False)
                result = await session.execute(stmt)
                appointment = result.scalars().all()

                if not appointment:
                    logger.info("Сценарии для отправки не найдены")
                    return []

                logger.info(f"Найдены сценарии для отправки")
                result = [
                    {
                        "id": appointments.id,
                        "client_id": appointments.client_id,
                        "doctor_id": appointments.doctor_id,
                        "procedure_id": appointments.procedure_id,
                        "start_time": appointments.start_time,
                        "end_time": appointments.end_time,
                        "room_name": appointments.room_name,
                    }
                    for appointments in appointment
                ]

                return result

            except Exception as e:
                logger.exception(f"Ошибка при получении новых записей: {e}")
                return None


async def mark_appointment_as_processed(appointment_id):
    """
    Выставление флага, что сценарий загружен в redis
    """
    async with SessionLocal() as session:
        async with session.begin():
            try:
                stmt = select(Appointment).where(Appointment.id == appointment_id)
                result = await session.execute(stmt)
                appointment = result.scalars().first()

                if not appointment:
                    logger.warning(f"Appointment with ID {appointment_id} not found")
                    return False

                appointment.processed = True
                await session.commit()
                logger.info(f"Appointment {appointment_id} marked as processed")
                return True

            except Exception as e:
                logger.exception(f"Ошибка при обновлении статуса записи: {e}")
                return False
