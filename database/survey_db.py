from database.constants_db import logger
from sqlalchemy.future import select
from configuration.config_db import SessionLocal
from database.models import Client, Survey, Appointment, Doctor

from sqlalchemy.orm import selectinload


async def get_survey_by_id(survey_id: int):
    """
    Получение опроса по его ID.
    """
    async with SessionLocal() as session:
        async with session.begin():
            try:
                stmt = select(Survey.file).where(Survey.id == survey_id)
                result = await session.execute(stmt)
                survey_file = result.scalar()

                if survey_file is None:
                    return {"result": {"code": 1, "err_msg": "Опрос не найден"}}

                return {"result": {"file": survey_file, "code": 0}}

            except Exception as e:
                logger.exception(f"Ошибка при получении опроса: {e}")
                return {"result": {"code": 1, "err_msg": str(e)}}


async def add_to_result_in_survey(tg_id: int, value: str):
    """
    Обновление поля survey_result для пациента по tg_id.
    """
    async with SessionLocal() as session:
        async with session.begin():
            try:
                # Находим клиента по tg_id
                stmt = select(Client).where(Client.tg_id == tg_id)
                res = await session.execute(stmt)
                client = res.scalars().first()

                if not client:
                    return {
                        "result": {
                            "code": 1,
                            "err_msg": "Пользователь с таким tg_id не найден",
                        }
                    }

                # Обновляем поле survey_result
                client.survey_result = value

                return {"result": {"code": 0, "message": "Данные успешно обновлены"}}

            except Exception as e:
                logger.exception(f"Ошибка при обновлении данных: {e}")
                return {"result": {"code": 1, "err_msg": str(e)}}


async def add_survey_answers(tg_id: int, answers: dict):
    """
    Добавление ответов на опрос в поле surveys_answers для пациента.
    """
    async with SessionLocal() as session:
        async with session.begin():
            try:
                # Находим клиента по tg_id
                stmt = select(Client).where(Client.tg_id == tg_id)
                res = await session.execute(stmt)
                client = res.scalars().first()

                if not client:
                    return {
                        "result": {
                            "code": 1,
                            "err_msg": "Пользователь с данным tg_id не найден",
                        }
                    }

                # Получаем существующие результаты
                existing_results = (
                    client.surveys_answers if client.surveys_answers is not None else []
                )
                # Добавляем новый ответ
                existing_results.append(answers)
                client.surveys_answers = existing_results

                return {"result": {"code": 0, "message": "Данные успешно обновлены"}}

            except Exception as e:
                logger.exception(f"Ошибка при добавлении ответов на опрос: {e}")
                return {"result": {"code": 1, "err_msg": str(e)}}


async def get_doctor_by_client_tg_id(client_tg_id: int):
    """
    Получение врача(ей) по tg_id пациента.
    Возвращает список докторов, связанных с пациентом через назначения.
    """
    async with SessionLocal() as session:
        async with session.begin():
            try:
                # Запрос с предварительной загрузкой связанных назначений и докторов
                stmt_client = (
                    select(Client)
                    .options(
                        selectinload(Client.appointments).selectinload(
                            Appointment.doctor
                        )
                    )
                    .where(Client.tg_id == client_tg_id)
                )
                res_client = await session.execute(stmt_client)
                client = res_client.scalars().first()

                if not client:
                    return {"result": {"code": 1, "err_msg": "Пациент не найден"}}

                if not client.appointments:
                    return {"result": {"code": 1, "err_msg": "Назначения не найдены"}}

                doctors = []
                for appointment in client.appointments:
                    doctor = appointment.doctor
                    if doctor and doctor.tg_id is not None:
                        # Используем только существующие поля таблицы doctors
                        doctors.append(
                            {
                                "id": doctor.id,
                                "first_name": doctor.first_name,
                                "last_name": doctor.last_name,
                                "specialty": doctor.specialty,
                                "phone_number": doctor.phone_number,
                                "tg_id": doctor.tg_id,
                            }
                        )

                if not doctors:
                    return {"result": {"code": 1, "err_msg": "Доктора не найдены"}}

                return {"result": {"doctors": doctors, "code": 0}}

            except Exception as e:
                logger.exception(f"Ошибка при получении врача по tg_id пациента: {e}")
                return {"result": {"code": 1, "err_msg": str(e)}}


async def get_client_name_by_tg_id(client_tg_id: int):
    """
    Получение имени, фамилии, номера телефона и стадии по tg_id пациента.
    """
    async with SessionLocal() as session:
        async with session.begin():
            try:
                stmt = select(
                    Client.first_name,
                    Client.last_name,
                    Client.phone_number,
                    Client.stage,
                ).where(Client.tg_id == client_tg_id)
                result = await session.execute(stmt)
                client_data = result.first()

                if not client_data:
                    return {"result": {"code": 1, "err_msg": "Клиент не найден"}}

                first_name, last_name, phone_number, stage = client_data
                first_name = first_name or "Имя не указано"
                last_name = last_name or "Фамилия не указана"
                phone_number = (
                    str(phone_number) if phone_number else "Телефон не указан"
                )
                stage = stage if stage is not None else "Сценарий не указан"

                return {
                    "result": {
                        "first_name": first_name,
                        "last_name": last_name,
                        "phone_number": phone_number,
                        "stage": stage,
                        "code": 0,
                    }
                }

            except Exception as e:
                logger.exception(f"Ошибка при получении имени пациента по tg_id: {e}")
                return {"result": {"code": 1, "err_msg": str(e)}}
