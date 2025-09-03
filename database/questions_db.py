from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.exc import SQLAlchemyError
from database.models import Client, PatientQuestion
import logging

logger = logging.getLogger(__name__)


async def get_patient_name_by_tg_id(tg_id: int, db_session: AsyncSession):
    """
    Получает имя и фамилию пациента по его Telegram ID.

    :param tg_id: Telegram ID пациента.
    :param db_session: Асинхронная сессия базы данных.
    :return: Словарь с first_name и last_name пациента или None, если пациент не найден.
    """
    # получаем фио пациента из clients по tg_id
    try:
        result = await db_session.execute(
            select(Client.first_name, Client.last_name).filter(Client.tg_id == tg_id)
        )
        patient = result.all()

        if patient:
            first_name, last_name = patient[0]
            return {"first_name": first_name, "last_name": last_name}
        else:
            return None
    except SQLAlchemyError as e:
        logger.exception(
            f"Ошибка при получении имени пациента из таблицы клиентов: {e}"
        )
        return None


async def save_question_to_db(
    patient_tg_id: int,
    first_name: str,
    last_name: str,
    question_text: str,
    db_session: AsyncSession,
):
    """
    Сохраняет вопрос пациента в базу данных.

    :param patient_tg_id: Telegram ID пациента.
    :param first_name: Имя пациента.
    :param last_name: Фамилия пациента.
    :param question_text: Текст вопроса.
    :param db_session: Асинхронная сессия базы данных.
    :return: Объект PatientQuestion, если успешно сохранено, иначе None.
    """
    now = datetime.utcnow()

    data = PatientQuestion(
        patient_tg_id=patient_tg_id,
        first_name=first_name,
        last_name=last_name,
        question_text=question_text,
        status=False,
        created_at=now,
        updated_at=now,
    )

    try:
        db_session.add(data)
        await db_session.commit()
        return data
    except SQLAlchemyError as e:
        await db_session.rollback()
        logger.exception(f"Ошибка при сохранении вопроса в базу данных: {e}")
        return None


async def has_unanswered_question(tg_id: int, db_session: AsyncSession):
    """
    Проверяет, есть ли у пациента неотвеченные вопросы.

    :param tg_id: Telegram ID пациента.
    :param db_session: Асинхронная сессия базы данных.
    :return: True, если есть неотвеченные вопросы, иначе False.
    """
    try:
        result = await db_session.execute(
            select(PatientQuestion).filter(
                PatientQuestion.patient_tg_id == tg_id, PatientQuestion.status == False
            )
        )
        unanswered_question = result.scalars().first()

        return unanswered_question is not None
    except SQLAlchemyError as e:
        logger.exception(f"Ошибка при проверке наличия неотвеченных вопросов: {e}")
        return False


async def is_question_answered(question_id: int, db_session: AsyncSession) -> bool:
    """
    Проверяет, был ли вопрос уже отвечен.

    :param question_id: ID вопроса.
    :param db_session: Асинхронная сессия базы данных.
    :return: True, если вопрос уже отвечен, иначе False.
    :raises: Исключение при ошибке запроса к базе данных.
    """
    try:
        result = await db_session.execute(
            select(PatientQuestion.status).filter(PatientQuestion.id == question_id)
        )
        question = result.scalars().first()

        if question is not None:
            return question
        else:
            logger.error(f"Вопрос с ID {question_id} не найден.")
            return False
    except SQLAlchemyError as e:
        logger.exception(f"Ошибка при проверке статуса вопроса: {e}")
        raise


async def update_question_response(
    question_id: int, support_response: str, db_session: AsyncSession
):
    """
    Обновляет статус вопроса, сохраняет ответ от службы поддержки.

    :param question_id: ID вопроса.
    :param support_response: Текст ответа от поддержки.
    :param db_session: Асинхронная сессия базы данных.
    :return: Обновленный объект PatientQuestion или None, если вопрос не найден.
    """
    data = {
        "status": True,  # вопрос закрыт
        "support_response": support_response,
        "updated_at": datetime.utcnow(),
    }

    try:
        result = await db_session.execute(
            select(PatientQuestion).filter(PatientQuestion.id == question_id)
        )
        question = result.scalars().first()

        if question:
            for key, value in data.items():
                setattr(question, key, value)

            await db_session.commit()
            return question
        else:
            logger.error(f"Вопрос с ID {question_id} не найден.")
            return None
    except SQLAlchemyError as e:
        await db_session.rollback()  # откат при ошибке
        logger.exception(f"Ошибка при сохранении ответа на вопрос в базу данных: {e}")
        return None


async def cancel_question_in_db(question_id: int, db_session: AsyncSession):
    """
    Отменяет вопрос пациента, устанавливая статус как закрытый.

    :param question_id: ID вопроса.
    :param db_session: Асинхронная сессия базы данных.
    :return: Обновленный объект PatientQuestion или None, если вопрос не найден.
    """
    data = {
        "status": True,  # вопрос закрыт
        "updated_at": datetime.utcnow(),
    }

    try:
        result = await db_session.execute(
            select(PatientQuestion).filter(PatientQuestion.id == question_id)
        )
        question = result.scalars().first()

        if question:
            # проходим по ключам и значениям в словаре data
            # и динамически обновляем соответствующие атрибуты объекта question
            for key, value in data.items():
                setattr(question, key, value)

            await db_session.commit()
            return question
        else:
            logger.error(f"Вопрос с ID {question_id} не найден.")
            return None
    except SQLAlchemyError as e:
        await db_session.rollback()  # откат в случае ошибки
        logger.exception(f"Ошибка при отмене вопроса в базе данных: {e}")
        return None
