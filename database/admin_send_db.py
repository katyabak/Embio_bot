from sqlalchemy.future import select
from database.models import Client, Appointment, Doctor, Scenario
from configuration.config_db import SessionLocal
import logging

logger = logging.getLogger(__name__)


async def find_id_doctor(tg_id):
    """
    Находит ID CRM врача, связанного с клиентом по tg_id.

    :param tg_id: Telegram ID клиента.
    :return: Словарь с ID врача в CRM или None, если врач не найден.
    """
    try:
        async with SessionLocal() as session:
            async with session.begin():
                # находим клиента по tg_id
                client_query = await session.execute(
                    select(Client).where(Client.tg_id == tg_id)
                )
                client = client_query.scalars().first()

                if not client:
                    logger.warning(f"Клиент с tg_id {tg_id} не найден.")
                    return None

                # находим запись
                appointment_query = await session.execute(
                    select(Appointment).where(Appointment.client_id == client.id)
                )
                appointment = appointment_query.scalars().first()

                if not appointment or not appointment.doctor_id:
                    logger.warning(
                        f"Назначение для клиента с ID {client.id} не найдено или не привязан доктор."
                    )
                    return None

                # находим ID CRM врача по doctor_id из записи
                doctor_query = await session.execute(
                    select(Doctor).where(Doctor.id == appointment.doctor_id)
                )
                doctor = doctor_query.scalars().first()

                if not doctor or not doctor.id_crm:
                    logger.warning(
                        f"Врач с ID {appointment.doctor_id} не найден или не имеет ID CRM."
                    )
                    return None

                return {"doctor_id": doctor.id_crm}

    except Exception as e:
        logger.exception(f"Ошибка при поиске врача: {e}")
        return None


async def get_general_scenarios():
    """
    Получение всех сценариев из базы данных.

    :return: Словарь с результатом (список сценариев) или None в случае ошибки.
    """
    async with SessionLocal() as session:
        try:

            scenarios_query = await session.execute(select(Scenario))
            scenarios = scenarios_query.scalars().all()

            if not scenarios:
                return None

            result = sorted(
                [
                    {
                        "scenario_id": scenario.id,
                        "name_stage": (
                            scenario.scenarios_msg.get("name_stage", "Без названия")
                            if scenario.scenarios_msg
                            else "Без названия"
                        ),
                    }
                    for scenario in scenarios
                ],
                key=lambda x: x["scenario_id"],  # Сортировка по ID этапа
            )

            return {"result": {"items": result, "code": 0}}

        except Exception as e:
            logger.exception(f"Ошибка при получении сценариев: {e}")
            return None


async def get_general_scenario_data(scenario_name):
    """
    Получение данных сценария по имени этапа (name_stage).

    :param scenario_name: Имя этапа, по которому ищем сценарий.
    :return: Данные сценария (JSON), если найден, иначе None.
    """
    async with SessionLocal() as session:
        try:
            scenarios_query = await session.execute(select(Scenario))
            scenarios = scenarios_query.scalars().all()

            if not scenarios:
                return None

            for scenario in scenarios:
                name_stage = scenario.scenarios_msg.get("name_stage", "")
                if name_stage == scenario_name:
                    return scenario.scenarios_msg

            return None

        except Exception as e:
            logger.exception(f"Ошибка при получении данных сценария: {e}")
            return None
