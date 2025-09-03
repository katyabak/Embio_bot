from sqlalchemy.future import select
from sqlalchemy.exc import SQLAlchemyError
from database.constants_db import logger
from configuration.config_db import SessionLocal
from database.models import Doctor, Appointment, Client


# Получение пациентов по номеру телефона доктора
async def get_patients_by_doctor_phone(phone: str):
    async with SessionLocal() as session:
        try:
            # Получаем ID доктора по номеру телефона
            doctor_query = await session.execute(
                select(Doctor.id).where(Doctor.phone_number == phone)
            )
            doctor_id = doctor_query.scalars().first()

            if not doctor_id:
                return {"result": {"code": 1, "err_msg": "Доктор не найден"}}

            # Получаем пациентов, которые записаны на приём к доктору
            appointments_query = await session.execute(
                select(
                    Client.first_name,
                    Client.last_name,
                    Client.tg_id,
                    Client.phone_number,
                    Client.stage,
                    Client.survey_result,
                )
                .join(Appointment, Appointment.client_id == Client.id)
                .where(Appointment.doctor_id == doctor_id)
            )
            patients_data = appointments_query.all()

            if not patients_data:
                return {"result": {"code": 1, "err_msg": "Пациенты не найдены"}}

            # Формируем список пациентов
            patients = [
                {
                    "first_name": patient.first_name,
                    "last_name": patient.last_name,
                    "tg_id": patient.tg_id,
                    "phone_number": patient.phone_number,
                    "stage": patient.stage,
                    "survey_result": patient.survey_result,
                }
                for patient in patients_data
            ]

            return {"result": {"patients": patients, "code": 0}}

        except SQLAlchemyError as e:
            logger.exception(f"Ошибка при получении пациентов по номеру врача: {e}")
            return {"result": {"code": 1, "err_msg": str(e)}}


# Получение ответов на опросы клиента по его номеру телефона
async def get_patient_surveys_answers_by_phone(phone: str):
    async with SessionLocal() as session:
        try:
            # Получаем данные клиента по номеру телефона
            client_query = await session.execute(
                select(Client.surveys_answers).where(Client.phone_number == phone)
            )
            surveys_answers = client_query.scalars().first()

            if not surveys_answers:
                return {"result": {"code": 1, "err_msg": "Ответы на опросы не найдены"}}

            return {"result": {"surveys_answers": surveys_answers, "code": 0}}

        except SQLAlchemyError as e:
            logger.exception(f"Ошибка при получении ответов на опросы клиента: {e}")
            return {"result": {"code": 1, "err_msg": str(e)}}
