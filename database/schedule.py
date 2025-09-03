from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from database.models import Client, Appointment, Procedure, Doctor
from database.constants_db import logger


async def get_schedule_by_tg_id(tg_id: int, session: AsyncSession):
    """
    Получает последнюю запись в расписании клиента по его Telegram ID.

    :param tg_id: Telegram ID клиента.
    :param session: Асинхронная сессия SQLAlchemy.
    :return: Словарь с расписанием клиента, включая дату, процедуру и врача.
    В случае ошибки возвращает сообщение об ошибке с кодом 1.
    """
    try:
        async with session.begin():
            result = await session.execute(
                select(Client.id).filter(Client.tg_id == tg_id)
            )
            client_data = result.scalars().first()

            if not client_data:
                return {"result": {"code": 1, "err_msg": "Клиент не найден"}}

            client_id = client_data

            # получаем последнюю запись по client_id
            result = await session.execute(
                select(
                    Appointment,
                    Procedure.name,
                    Doctor.first_name,
                    Doctor.last_name,
                    Doctor.middle_name,
                )
                .join(Procedure, Appointment.procedure_id == Procedure.id)
                .join(Doctor, Appointment.doctor_id == Doctor.id)
                .filter(Appointment.client_id == client_id)
                .order_by(Appointment.start_time.desc())  # сортируем время начала в порядке убывания
            )
            schedule_data = result.first()  # берем первую запись из отсортированного результата

            if not schedule_data:
                return {"result": {"code": 1, "err_msg": "Записи не найдены"}}

            # формируем нужный ответ с только необходимыми полями
            schedule_item = schedule_data
            result = {
                "start_time": schedule_item.Appointment.start_time,
                "procedure_name": schedule_item.name,
                "doctor_first_name": schedule_item.first_name,
                "doctor_last_name": schedule_item.last_name,
                "doctor_middle_name": schedule_item.middle_name,
            }

            return {"result": {"item": result, "code": 0}}

    except Exception as e:
        logger.exception(f"Ошибка при получении расписания: {e}")
        return {"result": {"code": 1, "err_msg": str(e)}}
