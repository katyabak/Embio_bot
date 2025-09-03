from database.constants_db import logger
import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import joinedload
from database.models import (
    Client,
    UserScenario,
    Scenario,
    Doctor,
    Appointment,
)
from configuration.config_db import SessionLocal


async def get_info_patient_number_surname(info, by_what):
    """
    Поиск пациента по номеру телефона или фамилии, а также получение информации о его враче.
    """
    async with SessionLocal() as session:
        async with session.begin():
            try:
                # Определяем поле фильтрации
                if by_what == "phone_number":
                    stmt = (
                        select(Client)
                        .options(
                            joinedload(Client.appointments).joinedload(
                                Appointment.doctor
                            )
                        )
                        .where(Client.phone_number == int(info))
                    )
                else:
                    stmt = (
                        select(Client)
                        .options(
                            joinedload(Client.appointments).joinedload(
                                Appointment.doctor
                            )
                        )
                        .where(Client.last_name == info)
                    )

                result = await session.execute(stmt)
                clients = result.unique().scalars().all()

                if not clients:
                    return None

                results = []
                for client in clients:
                    # Предполагается, что привязан хотя бы один прием (appointment)
                    # Если нет, информация о враче будет пустой
                    if client.appointments and client.appointments[0].doctor:
                        doctor = client.appointments[0].doctor
                        doctor_name = f"{doctor.first_name} {doctor.last_name}"
                    else:
                        doctor_name = ""

                    result_item = {
                        "patient_id": client.id,
                        "patient_name": f"{client.first_name or ''} {client.last_name or ''}".strip(),
                        "patient_phone": (
                            str(client.phone_number) if client.phone_number else ""
                        ),
                        "stage": client.stage if client.stage else "",
                        "doctor_name": doctor_name,
                    }
                    results.append(result_item)

                return {"result": {"items": results, "code": 0}}
            except Exception as e:
                logger.exception(f"Ошибка при поиске пациента: {e}")
                return None


async def find_all_doctors():
    """
    Получение списка всех врачей.
    """
    async with SessionLocal() as session:
        async with session.begin():
            try:
                stmt = select(Doctor)
                result = await session.execute(stmt)
                doctors = result.scalars().all()

                if not doctors:
                    return None

                items = [
                    {
                        "doctor_id": doctor.id,
                        "doctor_name": f"{doctor.first_name} {doctor.last_name}",
                    }
                    for doctor in doctors
                ]

                return {"result": {"items": items, "code": 0}}
            except Exception as e:
                logger.exception(f"Ошибка при получении списка врачей: {e}")
                return None


async def find_all_patients(doctor_id):
    """
    Получение всех пациентов у конкретного врача по doctor_id.
    """
    async with SessionLocal() as session:
        async with session.begin():
            try:
                # Выбираем все приемы конкретного врача, приджойниваем клиентов
                stmt = (
                    select(Appointment)
                    .options(joinedload(Appointment.client))
                    .where(Appointment.doctor_id == doctor_id)
                )

                result = await session.execute(stmt)
                appointments = result.scalars().all()

                if not appointments:
                    return None

                items = []
                # Извлекаем уникальных клиентов, так как у врача может быть несколько приемов с одним пациентом
                seen_clients = set()

                for appointment in appointments:
                    client = appointment.client
                    if client and client.id not in seen_clients:
                        seen_clients.add(client.id)
                        items.append(
                            {
                                "patient_id": client.id,
                                "patient_name": f"{client.first_name or ''} {client.last_name or ''}".strip(),
                                "patient_phone": (
                                    str(client.phone_number)
                                    if client.phone_number
                                    else ""
                                ),
                                "stage": client.stage if client.stage else "",
                            }
                        )

                return {"result": {"items": items, "code": 0}}

            except Exception as e:
                logger.exception(f"Ошибка при получении списка пациентов: {e}")
                return None


async def find_patient_scenarios(phone_number):
    """
    Поиск сценариев для клиента по номеру телефона.
    """
    async with SessionLocal() as session:
        async with session.begin():
            try:
                # Находим tg_id клиента по номеру телефона
                stmt_client = select(Client.tg_id).where(
                    Client.phone_number == int(phone_number)
                )
                client_result = await session.execute(stmt_client)
                tg_id = client_result.scalars().first()

                if not tg_id:
                    return {"error": "Клиент не найден"}

                # Находим пользовательские сценарии
                stmt_scenario = (
                    select(UserScenario)
                    .options(joinedload(UserScenario.client))
                    .where(UserScenario.clients_id == tg_id)
                )

                scenario_result = await session.execute(stmt_scenario)
                user_scenarios = scenario_result.scalars().all()

                if not user_scenarios:
                    return {"error": "Сценарии не найдены"}

                result = [
                    {
                        "scenario_id": scenario.id,
                        "messages": scenario.scenarios.get("messages", []),
                        "name_stage": scenario.scenarios.get("name_stage", ""),
                        "procedures": scenario.scenarios.get("procedures", []),
                    }
                    for scenario in user_scenarios
                ]

                return {"result": {"items": result, "code": 0}}

            except Exception as e:
                logger.exception(f"Ошибка при получении сценария пациента: {e}")
                return {"error": str(e)}


async def update_users_scenario(
    scenario_id: int, data_to_update: dict, table_name: str
):
    """
    Обновление сценария в базе данных по ID сценария.
    """
    async with SessionLocal() as session:
        async with session.begin():
            try:
                if table_name == "users":
                    stmt = select(UserScenario).where(UserScenario.id == scenario_id)
                elif table_name == "general":
                    stmt = select(Scenario).where(Scenario.id == scenario_id)
                else:
                    return {"status": "error", "message": "Некорректное имя таблицы."}

                result = await session.execute(stmt)
                scenario = result.scalars().first()

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


async def get_all_scenarios():
    """
    Получение всех сценариев из базы данных.
    """
    async with SessionLocal() as session:
        async with session.begin():
            try:
                stmt = select(Scenario)
                result = await session.execute(stmt)
                scenarios = result.scalars().all()

                if not scenarios:
                    return None

                items = sorted(
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
                    key=lambda x: x["scenario_id"],
                )

                return {"result": {"items": items, "code": 0}}

            except Exception as e:
                logger.exception(f"Ошибка при получении сценариев: {e}")
                return None


async def get_scenario_data(scenario_name):
    """
    Получение данных сценария по имени этапа (name_stage).
    """
    async with SessionLocal() as session:
        async with session.begin():
            try:
                stmt = select(Scenario)
                result = await session.execute(stmt)
                general_scenarios = result.scalars().all()

                if not general_scenarios:
                    return None

                # Ищем сценарий с нужным name_stage
                for scenario in general_scenarios:
                    name_stage = (
                        scenario.scenarios_msg.get("name_stage", "")
                        if scenario.scenarios_msg
                        else ""
                    )
                    if name_stage == scenario_name:
                        # Вернем все сценарии, у которых имя совпадает (хотя, возможно, стоит возвращать один)
                        filtered = [
                            {
                                "scenario_id": s.id,
                                "messages": (
                                    s.scenarios_msg.get("messages", [])
                                    if s.scenarios_msg
                                    else []
                                ),
                                "name_stage": (
                                    s.scenarios_msg.get("name_stage", "")
                                    if s.scenarios_msg
                                    else ""
                                ),
                                "procedures": (
                                    s.scenarios_msg.get("procedures", [])
                                    if s.scenarios_msg
                                    else []
                                ),
                            }
                            for s in general_scenarios
                            if s.scenarios_msg
                            and s.scenarios_msg.get("name_stage", "") == scenario_name
                        ]
                        return {"result": {"items": filtered, "code": 0}}

                return None

            except Exception as e:
                logger.exception(f"Ошибка при получении данных сценария: {e}")
                return None


# Эти функции предполагают логику редактирования сообщений по сценарию,
# для их корректной работы нужно соответствующее использование в коде приложения.
async def save_edited_message(scenario_id, unique_messages):
    # Предполагается, что мы обновляем сценарий в таблице general (Scenario)
    data_to_update = {"scenarios": {"messages": unique_messages}}
    # В данном случае для сохранения изменений в сценарий нужно извлечь весь сценарий,
    # добавить измененные сообщения и обновить.
    # Предполагается, что сценарий уже есть, и мы хотим обновить scenarios_msg.
    async with SessionLocal() as session:
        async with session.begin():
            stmt = select(Scenario).where(Scenario.id == scenario_id)
            result = await session.execute(stmt)
            scenario = result.scalars().first()

            if not scenario or not scenario.scenarios_msg:
                raise Exception("Сценарий не найден или не содержит данных")

            scenario.scenarios_msg["messages"] = unique_messages
            await session.commit()


async def save_edited_time(scenario_id, message_id, new_time, unique_messages):
    # Находим нужное сообщение и обновляем время
    for message in unique_messages:
        if message.get("id") == message_id:
            message["time"] = new_time
            break

    await save_edited_message(scenario_id, unique_messages)


async def find_id_doctor(tg_id):
    """
    Поиск id_crm врача по tg_id пациента через Appointment.
    """
    async with SessionLocal() as session:
        async with session.begin():
            try:
                # Находим клиента по tg_id
                stmt_client = select(Client).where(Client.tg_id == tg_id)
                res_client = await session.execute(stmt_client)
                client = res_client.scalars().first()

                if not client:
                    return None

                # Находим Appointment для клиента
                stmt_appointments = (
                    select(Appointment)
                    .options(joinedload(Appointment.doctor))
                    .where(Appointment.client_id == client.id)
                )
                res_appointments = await session.execute(stmt_appointments)
                appointment = res_appointments.scalars().first()

                if not appointment or not appointment.doctor:
                    return None

                doctor = appointment.doctor
                doctor_id = doctor.id_crm
                return {"doctor_id": doctor_id}

            except Exception as e:
                logger.exception(f"Ошибка при поиске врача: {e}")
                return None
