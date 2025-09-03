import re
import logging
import os
from aiogram import types
from aiogram.fsm.context import FSMContext
import html
from sqlalchemy.future import select
from database.models import PatientQuestion
from database.questions_db import (
    save_question_to_db,
    get_patient_name_by_tg_id,
)
from configuration.config_db import SessionLocal
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession

load_dotenv()
logger = logging.getLogger(__name__)
support_group_id = os.getenv("SUPPORT_GROUP_ID")


def markdown_escape(text: str) -> str:
    """
    Экранирует специальные символы в тексте для безопасного использования в HTML.

    :param text: Текст, который нужно экранировать.
    :return: Экранированный текст.
    """

    return html.escape(text)


async def send_question_to_support(message: types.Message, state: FSMContext):
    """
    Отправляет вопрос пациента в службу поддержки и сохраняет его в БД.

    :param message: Сообщение с текстом вопроса от пациента.
    :param state: Состояние машины состояний для сохранения данных.
    :return: Сообщение о результате операции, отправленное пациенту.
    """
    user_id = message.from_user.id
    question_text = message.text
    async with SessionLocal() as db_session:
        patient_name = await get_patient_name_by_tg_id(user_id, db_session)

    if not patient_name:
        first_name = "Без имени"
        last_name = ""
    else:
        first_name = patient_name["first_name"]
        last_name = patient_name["last_name"]

    response = await save_question_to_db(
        user_id, first_name, last_name, question_text, db_session
    )

    if response:
        question_id = response.id
        status = "открыт✅"

        support_message = (
            f"❓Вопрос №{question_id}.\n\n"
            f"Пациент: {markdown_escape(first_name)} {markdown_escape(last_name)}\n"
            f"Вопрос: {markdown_escape(question_text)}\n\n"
            f"Статус вопроса: {status}\n\n"
            f"Ответьте на это сообщение, чтобы отправить ответ пациенту."
        )

        support_msg = await message.bot.send_message(
            support_group_id, support_message, parse_mode="HTML"
        )

        await state.update_data(
            support_msg_id=support_msg.message_id, question_id=question_id
        )

        await message.answer(
            "Ваш вопрос был отправлен в службу поддержки. Мы свяжемся с вами как можно скорее."
        )
    else:
        await message.answer(
            "Произошла ошибка при отправке вашего вопроса. Пожалуйста, попробуйте снова."
        )


def extract_question_id_from_message(text: str) -> int:
    """
    Извлекает ID вопроса из текста сообщения.

    :param text: Текст сообщения, из которого нужно извлечь ID вопроса.
    :return: ID вопроса, если найден, или вызывает ошибку, если не удалось извлечь ID.
    """
    # Ищем ID после "Вопрос №" и перед первым символом ':'
    match = re.search(r"Вопрос №(\d+).", text)
    if match:
        return int(match.group(1))
    else:
        logger.error("Не удалось извлечь ID вопроса из текста сообщения.")


async def get_patient_tg_id_from_question_id(
    question_id: int, db_session: AsyncSession
) -> int:
    """
    Получает Telegram ID пациента по ID вопроса из БД.

    :param question_id: ID вопроса.
    :param db_session: Сессия БД для выполнения запроса.
    :return: Telegram ID пациента, если найден, или вызывает ошибку, если не найден.
    """
    try:
        result = await db_session.execute(
            select(PatientQuestion.patient_tg_id).filter(
                PatientQuestion.id == question_id
            )
        )
        patient = result.scalars().first()

        if patient:
            return patient
        else:
            logger.error("Пациент с данным ID вопроса не найден.")
    except Exception as e:
        logger.exception(f"Error retrieving patient TG ID: {e}")
        raise
