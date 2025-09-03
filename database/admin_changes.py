from sqlalchemy.future import select
from sqlalchemy.orm import joinedload

from configuration.config_db import SessionLocal
from database.constants_db import logger
from database.models import (
    Client,
    UserScenario,
    Scenario,
)


async def get_all_scenarios():
    """
    Получение всех сценариев из базы данных.

    :return: Словарь с результатом или None в случае ошибки.
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
                            scenario.scenarios_msg.get("name_stage", "")
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


async def find_patient_scenarios(phone_number):
    """
    Поиск сценариев для клиента по номеру телефона.

    :param phone_number: Номер телефона клиента.
    :return: Словарь с результатом или ошибкой.
    """
    async with SessionLocal() as session:
        try:
            client_query = await session.execute(
                select(Client.tg_id).where(Client.phone_number == int(phone_number))
            )
            tg_id = client_query.scalars().first()

            if not tg_id:
                return {"error": "Клиент не найден"}

            scenarios_query = await session.execute(
                select(UserScenario)
                .options(joinedload(UserScenario.client))
                .where(UserScenario.clients_id == tg_id)
            )
            user_scenarios = scenarios_query.scalars().all()

            if not user_scenarios:
                return {"error": "Сценарии не найдены"}

            result = [
                {
                    "scenario_id": scenario.id,
                    "messages": scenario.scenarios.get("messages"),
                    "name_stage": scenario.scenarios.get("name_stage", ""),
                    "procedures": scenario.scenarios.get("procedures"),
                }
                for scenario in user_scenarios
            ]

            return {"result": {"items": result, "code": 0}}

        except Exception as e:
            logger.exception(f"Ошибка при получении сценария пациента: {e}")
            return {"error": str(e)}


async def get_scenario_data(scenario_name):
    """
    Получение данных сценария по имени этапа (name_stage).

    :param scenario_name: Имя этапа, по которому ищем сценарий.
    :return: Данные сценария (JSON), если найден, иначе None.
    """
    async with SessionLocal() as session:
        try:
            scenarios_query = await session.execute(select(Scenario))
            general_scenarios = scenarios_query.scalars().all()

            if not general_scenarios:
                return None

            for scenario in general_scenarios:
                name_stage = scenario.scenarios_msg.get("name_stage", "")
                if name_stage == scenario_name:
                    result = [
                        {
                            "scenario_id": scenario.id,
                            "messages": scenario.scenarios_msg.get("messages"),
                            "name_stage": scenario.scenarios_msg.get("name_stage", ""),
                            "procedures": scenario.scenarios_msg.get("procedures"),
                        }
                    ]
                    return {"result": {"items": result, "code": 0}}

            return None

        except Exception as e:
            logger.exception(f"Ошибка при получении данных сценария: {e}")
            return None


async def update_users_scenario(
        scenario_id: int, data_to_update: dict, table_name: str
):
    """
    Обновление сценария в базе данных по ID сценария.

    :param scenario_id: ID сценария для обновления.
    :param data_to_update: Готовые данные для обновления (сценарий в формате JSON).
    :return: Словарь с результатом операции.
    """
    async with SessionLocal() as session:
        try:
            if table_name == "users":
                scenario_query = await session.execute(
                    select(UserScenario).where(UserScenario.id == scenario_id)
                )
            elif table_name == "general":
                scenario_query = await session.execute(
                    select(Scenario).where(Scenario.id == scenario_id)
                )

            scenario = scenario_query.scalars().first()

            if not scenario:
                return {
                    "status": "error",
                    "message": "Сценарий с указанным ID не найден.",
                }

            scenarios_data = data_to_update.get("scenarios", [])
            if table_name == "users":
                scenario.scenarios = scenarios_data
            elif table_name == "general":
                scenario.scenarios_msg = scenarios_data

            await session.commit()

            return {"status": "success", "message": "Сценарий успешно обновлен."}
        except Exception as e:
            logger.exception(f"Ошибка при обновлении сценария: {e}")
            return {"status": "error", "message": str(e)}
