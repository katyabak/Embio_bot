import logging
import os
from datetime import datetime, timedelta

from aiogram.types import Message

from configuration.config_crm import get_information
from keyboards.auth_kb import get_approve_keyboard

logger = logging.getLogger(__name__)
support_group_id = os.getenv("SUPPORT_GROUP_ID")


async def get_user_data(phone):
    """
    Получает данные пациента по номеру телефона.

    :param phone: Номер телефона пользователя.
    :return: Ответ с данными пользователя, полученными от CRM.
    """
    data = {"command": "get_user_data", "user": phone}
    return await get_information(data)


async def get_sotr_data(phone):
    """
    Получает данные врача по номеру телефона.

    :param phone: Номер телефона сотрудника.
    :return: Ответ с данными сотрудника, полученными от внешнего сервиса.
    """
    data = {"command": "get_sotr", "phone": phone}
    return await get_information(data)


async def get_book_data(client_id):
    """
    Получает данные о записях пациента на основе его ID.

    :param client_id: ID клиента.
    :return: Ответ с данными о записях клиента на основе заданного периода.
    """
    today = datetime.today()
    beg_per = (today - timedelta(days=2)).strftime("%d.%m.%Y")
    end_per = (today + timedelta(days=4)).strftime("%d.%m.%Y")

    data = {
        "command": "get_book",
        "id": client_id,
        "beg_per": beg_per,
        "end_per": end_per,
    }

    return await get_information(data)


async def authenticate_patient(phone, state):
    """
    Аутентифицирует пациента по номеру телефона и сохраняет информацию в состояние.

    :param phone: Номер телефона пациента.
    :param state: Состояние, в котором сохраняется информация о пациенте.
    :return: True, если аутентификация прошла успешно, иначе False.
    """
    response = await get_user_data(phone)
    if response.get("result", {}).get("code") == 0:
        user_info = response["result"]
        client_id = user_info["id"]
        await state.update_data(
            name=user_info["name"],
            passport=0,
            id_crm=client_id,
        )
        return True

    return False


async def authenticate_doctor(phone, state):
    """
    Аутентифицирует врача по номеру телефона и сохраняет информацию в состояние.

    :param phone: Номер телефона врача.
    :param state: Состояние, в котором сохраняется информация о враче.
    :return: True, если аутентификация прошла успешно, иначе False.
    """
    response = await get_sotr_data(phone)
    if response.get("result", {}).get("code") == 0:
        sotr_info = response["result"]["item"]
        await state.update_data(
            name=sotr_info["full_name"],
            specialty=sotr_info["dolj"],
            id_crm=sotr_info["id"],
        )
        return True
    return False


async def replace_content(
        start_time, message, first_name_clients, first_name_doctor, last_name_doctor
):
    """
    Замена флагов в сообщении, которые находятся в {}

    :param start_time - время начала процедуры
    :param message - сообщение, которое нужно изменить
    :param first_name_clients - Имя клиента
    :param first_name_doctor - Имя доктора
    :param last_name_doctor - Фамилия доктора
    :return отредактированное сообщение
    """
    try:
        if start_time != None:
            if isinstance(start_time, datetime):
                start_time_str = start_time.strftime(
                    "%Y-%m-%dT%H:%M:%S%z"
                )  # Формат с временем и смещением
            else:
                start_time_str = start_time
            formats = [
                "%Y-%m-%dT%H:%M:%S",
                "%d.%m.%Y %H:%M",
                "%Y-%m-%d %H:%M:%S",
            ]
            start_time_datetime = None
            for fmt in formats:
                try:
                    start_time_datetime = datetime.strptime(start_time_str, fmt)
                    break
                except ValueError:
                    continue

            if not start_time_datetime:
                return message

            day = start_time_datetime.strftime("%d.%m")
            month_and_time = start_time_datetime.strftime("%H:%M")
            formatted_start_time = f"{day} в {month_and_time}"

        else:
            formatted_start_time = None

        placeholders = {
            "{first_name}": first_name_clients,
            "{first_name_doctor}": first_name_doctor,
            "{last_name_doctor}": last_name_doctor,
            "{start_time}": formatted_start_time,
        }

        content = message.get("content", "")
        for placeholder, value in placeholders.items():
            if placeholder in content:
                content = content.replace(placeholder, value)
        message["content"] = content

        if "time" in message:
            time_content = message.get("time", "")
            for placeholder, value in placeholders.items():
                if placeholder in time_content:
                    time_content = time_content.replace(placeholder, value)
            message["time"] = time_content

        return message
    except Exception as e:
        return message


def validate_phone_number(phone_number: str) -> str:
    """
    Проверяет и исправляет формат телефонного номера.

    :param phone_number: Номер телефона, полученный от пользователя.

    :return: Номер телефона в формате +7XXXXXXXXXX.
    """
    if not phone_number.startswith("+"):
        phone_number = f"+{phone_number}"

    return phone_number


async def send_access_request_to_support(message: Message, phone: str, role: str):
    """
    Отправляет запрос на доступ в поддержку с данными пользователя.

    :param message: Сообщение от пользователя.
    :param phone: Номер телефона пользователя, привязанный к учетной записи.
    :param role: Роль пользователя (Пациент/Доктор).
    :return: None
    """
    try:
        request_text = (
            f"Запрос на доступ\n"
            f"chat_id: {message.chat.id}\n"
            f"Пользователь: @{message.from_user.username}\n"
            f"Телефон СРМ: {phone}\n"
            f"Роль: {role}"
        )

        inline_keyboard = get_approve_keyboard(message.chat.id, role, phone)

        await message.bot.send_message(
            chat_id=support_group_id,
            text=request_text,
            reply_markup=inline_keyboard,
        )
    except Exception as e:
        logger.error(f"Ошибка при отправке запроса в поддержку: {e}")
        await message.answer("Произошла ошибка при отправке запроса в поддержку.")
