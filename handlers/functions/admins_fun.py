import logging
import re
from typing import Optional, List

from aiogram.types import (
    Message,
    MessageEntity,
    UNSET_PARSE_MODE,
    InputMedia,
    InputMediaPhoto,
    InputMediaAudio,
    InputMediaVideo,
    InputMediaDocument,
    InputMediaAnimation,
)

import keyboards.admin_kb as kb
import keyboards.constants as kc
from configuration.config_bot import bot
from database.admin_changes import get_scenario_data, update_users_scenario
from database.admin_db import get_info_patient_number_surname
from database.constants_db import stage_number_to_name
from states.states_admin import (
    AdminStates_global,
    AdminStates_find,
)

logger = logging.getLogger(__name__)


def to_input_media(
        message: Message,
        caption: Optional[str] = None,
        parse_mode: Optional[str] = UNSET_PARSE_MODE,
        caption_entities: Optional[List[MessageEntity]] = None,
) -> InputMedia:
    if message.content_type == "photo":
        cls = InputMediaPhoto
        media = message.photo[0].file_id
    elif message.content_type == "video":
        cls = InputMediaVideo
        media = message.video.file_id
    elif message.content_type == "audio":
        cls = InputMediaAudio
        media = message.audio.file_id
    elif message.content_type == "document":
        cls = InputMediaDocument
        media = message.document.file_id
    elif message.content_type == "sticker":
        cls = InputMediaDocument
        media = message.sticker.file_id
    elif message.content_type == "voice":
        cls = InputMediaAudio
        media = message.voice.file_id
    elif message.content_type == "video_note":
        cls = InputMediaAudio
        media = message.video_note.file_id
    elif message.content_type == "animation":
        cls = InputMediaAnimation
        media = message.animation.file_id
    else:
        raise ValueError(f"Неподдерживаемый тип контента: {message.content_type}")
    caption_message = caption or message.caption
    return cls(
        media=media,
        caption=caption or message.html_text,
        parse_mode=parse_mode,
        caption_entities=caption_entities or message.caption_entities,
    )


async def format_message(chat_id, index, message):
    """Отправка админу контента и сообщений из сценария"""
    content = message.get("content", "")
    url = message.get("url", "")
    time = message.get("time", "")
    file_type = message.get("type")
    formatted_message = f"{index}. {content}"
    if time and time != "0":
        formatted_message += f"\n(Время отправки: {time})"
    match file_type:
        case "text":
            await bot.send_message(chat_id=chat_id, text=formatted_message, parse_mode='HTML')
        case "photo":
            await bot.send_photo(chat_id=chat_id, photo=url, caption=formatted_message, parse_mode='HTML')
        case "video":
            if url == "":
                formatted_message += f"\n(Тип контента: видео)"
                await bot.send_message(chat_id=chat_id, text=formatted_message, parse_mode='HTML')
            else:
                await bot.send_video(chat_id=chat_id, video=url, caption=formatted_message, parse_mode='HTML')
        case "survey":
            formatted_message += f"\n(Тип контента: опрос)"
            await bot.send_message(chat_id=chat_id, text=f"{formatted_message}", parse_mode='HTML')


def parse_time(time_str):
    """
    Парсит время из строки в формат времени в секундах.
    Возможные форматы:
    - "+/-24" — относительное время в часах от события.
    - "+/-24 10:00" — смещение в часах и точное время.
    - "0 10:00" — точное время в формате день и часы:минуты.
    - "0" — отправляется в день события (считается временем события).
    """

    match = re.match(r"([+-]?\d+)(?:\s+(\d{1,2}):(\d{2}))?", time_str)
    if match:
        day_offset = int(match.group(1))  # Смещение дней
        hours = (
            int(match.group(2)) if match.group(2) else 0
        )  # Если часы не указаны, установить 0
        minutes = (
            int(match.group(3)) if match.group(3) else 0
        )  # Если минуты не указаны, установить 0

        return day_offset * 86400 + hours * 3600 + minutes * 60

    elif time_str.startswith("+") or time_str.startswith("-"):
        try:
            return int(time_str) * 3600
        except ValueError:
            raise ValueError(f"Ошибка в формате времени: {time_str}")

    elif " " in time_str:
        day, clock_time = time_str.split()
        day_offset = int(day)
        hours, minutes = map(int, clock_time.split(":"))
        return day_offset * 86400 + hours * 3600 + minutes * 60

    return 0


async def format_scenarios(chat_id, current_part, scenarios, max_message_length=4096):
    response_parts = []

    for scenario in scenarios:
        # Убираем дублирующиеся сообщения
        unique_messages = {msg["id"]: msg for msg in scenario["messages"]}

        # Сортируем сообщения по времени, используя парсер времени
        sorted_messages = sorted(
            unique_messages.values(), key=lambda x: parse_time(x["time"])
        )

        # Формируем ответы с правильной нумерацией
        for i, message in enumerate(sorted_messages):
            formatted_message = await format_message(chat_id, i + 1, message)


async def choose_general_scenario(name_stage, message):
    """
    Получение общего сценария из бд

    :param name_stage - название этапа
    """
    scenario_data = await get_scenario_data(name_stage)
    if not scenario_data or not scenario_data.get("result", {}).get("items"):
        await message.answer(
            "В сожалению, такой сценарий отсутствует в базе данных. Попробуйте выбрать другой"
        )
        return None

    await format_scenarios(message.chat.id, "", scenario_data["result"]["items"])
    return scenario_data


async def edditing_message_or_time(choice, message):
    """
    Отправка сообщения о редактировании времени или сообщения

    :param choice - выбор пользователя после нажатия на кнопку
    """
    if choice == kc.buttons_time_or_msg["message"]:
        await message.answer(
            "Теперь начните вводить текст или вставьте ссылку на видео/изображение",
            reply_markup=kb.back_to_menu_kb(),
        )
    elif choice == kc.buttons_time_or_msg["time"]:
        await message.answer(
            "Теперь введите новое время в формате: (+/-)2 10:00",
            reply_markup=kb.back_to_menu_kb(),
        )
        await message.answer(
            "Где:\n +/- - обозначение после поцедуры и до соотвественно.\n2 - количество суток. Если отправка в тот "
            "же день, что и процедура, напишите 0\n10:00 - точное время отправки.\nЕсли какой-то из параметров "
            "отсутствует писать что-либо не обязательно."
        )


async def delete_and_shift_messages(scenarios, message_id, table_name):
    """
    Удаляет сообщение по ID из сценария, смещает остальные сообщения и сохраняет их в отдельной переменной.

    :param scenario: Сценарий, содержащий структуру messages.
    :param message_id: ID сообщения, которое нужно удалить.
    :return: Обновленный сценарий с измененными messages и переменная с удаленными данными.
    """
    scenario = scenarios["result"]["items"][0]

    # Удаляем сообщение с указанным ID
    scenario["messages"] = [
        msg for msg in scenario["messages"] if msg["id"] != message_id
    ]

    # Смещаем ID сообщений
    for index, message in enumerate(scenario["messages"], start=1):
        message["id"] = index

    # Обновляем messages_ids
    new_message_ids = [message["id"] for message in scenario["messages"]]
    scenario["messages_ids"] = new_message_ids

    if scenario.get("procedures"):
        # Синхронизация messages_ids в процедурах
        for procedure in scenario.get("procedures", []):
            procedure["message_ids"] = [
                msg_id for msg_id in procedure["message_ids"] if msg_id in new_message_ids
            ]

    # Подготовка данных для сохранения
    updated_scenario = {
        "messages": scenario["messages"],
        "messages_ids": scenario["messages_ids"],
        "name_stage": scenario.get("name_stage", ""),
        "procedures": scenario.get("procedures", []),
    }

    # Обновляем данные в базе
    result = await update_users_scenario(
        scenario["scenario_id"], {"scenarios": updated_scenario}, table_name
    )
    if result.get("status") == "success":
        return {
            "status": "success",
            "code": 0,
        }
    else:
        logger.error(f"Ошибка при обновлении сценария")
        return {"status": "error", "message": "Failed to update scenario"}


async def edditing_content(
        choice,
        message,
        edditing_text,
):
    """
    Проврека и вывод контента, который будет изменен в функции редактирования админа
    """
    if choice == kc.buttons_time_or_msg["message"]:
        url, content = '', ''
        if message.content_type != "text":
            get_captions = to_input_media(message)
            url = get_captions.media
            content = get_captions.caption
        await message.answer(
            f"Изменяю сообщение в текущем сценарии на следующее: "
        )
        if message.content_type == "photo":
            await message.answer_photo(photo=url, caption=content, parse_mode='HTML')
        elif message.content_type == "video":
            await message.answer_video(video=url, caption=content, parse_mode='HTML')
        else:
            await message.answer(edditing_text, parse_mode='HTML')
        valid = True
        return valid
    elif choice == kc.buttons_time_or_msg["time"]:
        # Регулярное выражение для проверки формата времени
        time_pattern = r"([+-]?\d+)(?:\s+(\d{1,2}):(\d{2}))?"

        if re.match(time_pattern, edditing_text):
            await message.answer(
                f"Изменяю время отправки на следующее: {edditing_text}"
            )
            valid = True
        else:
            await message.answer(
                "Некорректный формат времени. Пожалуйста, введите в формате: (+/-)2 10:00 или (+/-)2"
            )
            valid = False
        return valid


async def check_number_msg(number, scenarios, message, by_what):
    """
    Проверка корректности номера сообщения и его наличия в сценарии (для редактирования и удаления)
    """
    if number.isdigit() and any(
            1 <= int(number) <= len(scenario["messages"])
            for scenario in scenarios["result"]["items"]
    ):
        found_message = next(
            (
                msg
                for scenario in scenarios["result"]["items"]
                for msg in scenario["messages"]
                if msg["id"] == int(number)
            ),
            None,
        )
        if by_what == "edit":
            await message.answer(
                f"Вы выбрали сообщение для редактирования: ",
                reply_markup=kb.back_to_menu_kb(),
            )
            if found_message['type'] == "photo":
                await message.answer_photo(photo=found_message['url'], caption=found_message['content'],
                                           parse_mode='HTML')
            elif found_message['type'] == "video":
                await message.answer_video(video=found_message['url'], caption=found_message['content'],
                                           parse_mode='HTML')
            else:
                await message.answer(found_message['content'], parse_mode='HTML')
            await message.answer(f"Время отправки сообщения: {found_message['time']}", parse_mode='HTML')
            await message.answer(
                "Теперь скажите, что вы хотите изменить: время отправки или содержимое сообщения?",
                reply_markup=kb.edit_global_choice_keyboard(),
            )
        elif by_what == "delete":
            await message.answer(
                f"Вы выбрали сообщение для удаления:",
                reply_markup=kb.back_to_menu_kb(),
            )
            if found_message['type'] == "photo":
                await message.answer_photo(photo=found_message['url'], caption=found_message['content'],
                                           parse_mode='HTML')
            elif found_message['type'] == "video":
                await message.answer_video(video=found_message['url'], caption=found_message['content'],
                                           parse_mode='HTML')
            else:
                await message.answer(found_message['content'], parse_mode='HTML')

            await message.answer(f"Время отправки сообщения: {found_message['time']}")
            await message.answer(
                "Теперь скажите, вы уверены в своём выборе?",
                reply_markup=kb.yes_no_keyboard(),
            )
        return True
    else:
        await message.answer(
            "Сообщение с указанным номером не существует. Пожалуйста, введите корректный номер сообщения."
        )
        return False


def edit_time(editing_text):
    """
    Приведение времени к корректному формату времени
    """
    # Разделяем введённое время на две части
    time_parts = editing_text.split()
    try:
        # Сохраняем знак и преобразуем значение с учетом знака
        first_time = time_parts[0]
        if first_time[0] in ["+", "-"]:
            sign = first_time[0]
            number_part = int(first_time[1:]) * 24
            first_time = f"{sign}{number_part}"
        else:
            first_time = str(int(first_time) * 24)

        second_time = time_parts[1] if len(time_parts) > 1 else ""
        if first_time == "0" or second_time == "":
            full_time = f"{first_time}"
        else:
            full_time = f"{first_time} {second_time}"
        return full_time
    except (ValueError, IndexError):
        logger.error(f"Ошибка в формате времени")
        return {"status": "error", "message": "Invalid time format"}


async def changin_scenario_in_bd(scenarios, number, editing_text, by_what, table_name):
    """
    Подготовка сценария к сохранию в бд. Функция для редактирования отдельно времени и контента в сообщении

    :param scenario: Сценарий, содержащий структуру messages.
    :param number: Номер сообщения.
    :param editing_text: Редактируемый текст.
    :param by_what: Выбор пользователя - что редактируется время или сообщение.
    :param table_name: Таблица в которую сохраняется.
    """
    for scenario in scenarios["result"]["items"]:
        number = int(number)
        message = next(
            (msg for msg in scenario["messages"] if msg["id"] == number), None
        )
        if message:
            if by_what == kc.buttons_time_or_msg["message"]:
                if editing_text.content_type != "text":
                    get_captions = to_input_media(editing_text)
                    url = get_captions.media
                    content = get_captions.caption
                    file_type = editing_text.content_type
                    if content is None:
                        content = ""
                    message["content"] = content
                    if url:
                        message["url"] = url
                    else:
                        message.pop("url", None)
                    message["type"] = file_type
                else:
                    message["content"] = editing_text.html_text
                    message["type"] = editing_text.content_type

            elif by_what == kc.buttons_time_or_msg["time"]:
                edit_message = edit_time(editing_text.text)
                if not edit_message:
                    return edit_message
                else:
                    message["time"] = edit_message

            scenario["messages"].sort(key=lambda msg: parse_time(msg["time"]))

            for idx, msg in enumerate(scenario["messages"], start=1):
                msg["id"] = idx

            data_to_update = {
                "messages": scenario["messages"],
                "name_stage": scenario.get("name_stage", ""),
                "procedures": scenario.get("procedures", []),
            }

            try:
                result = await update_users_scenario(
                    scenario["scenario_id"], {"scenarios": data_to_update}, table_name
                )
                # Проверяем результат обновления данных
                if result.get("status") == "success":
                    scenarios["result"]["items"] = [{
                        "scenario_id": scenario["scenario_id"],
                        **data_to_update
                    }]
                    return {"status": "success", "code": 0, "scenario": scenarios}
                else:
                    logger.error(f"Ошибка при обновлении сценария")
                    return {"status": "error", "message": "Failed to update scenario"}
            except Exception as e:
                logger.error(f"Ошибка при запросе к Supabase: {e}")
                return {"status": "error", "message": str(e)}

    logger.error(f"Сообщение не было найдено")
    return {"status": "error", "message": "Message not found"}


async def add_message_to_scenario(
        scenarios, scenario_id, edit_content, time, url, type, table_name
):
    """
    Добавляет новое сообщение в конец списка сообщений указанного сценария.

    :param scenarios: Список сценариев.
    :param scenario_id: ID сценария, в который добавляется сообщение.
    :param content: Текст сообщения, включая URL.
    :param time: Время сообщения в одном из поддерживаемых форматов.
    :param table_name: Название таблицы для сохранения изменений.
    :return: Статус операции.
    """
    for scenario in scenarios["result"]["items"]:
        if scenario["scenario_id"] == scenario_id:

            # Формируем новое сообщение
            new_message = {
                "id": None,
                "content": edit_content,
                "time": edit_time(time),
                "type": type,
            }
            if url:
                new_message["url"] = url
                # Разделяем введённое время на две части

            scenario["messages"].append(new_message)
            scenario["messages"].sort(key=lambda msg: parse_time(msg["time"]))

            # Обновляем ID сообщений в соответствии с их новым порядком
            for idx, message in enumerate(scenario["messages"], start=1):
                message["id"] = idx

            # Подготовка данных для обновления в базе
            data_to_update = {
                "messages": scenario["messages"],
                "name_stage": scenario.get("name_stage", ""),
                "procedures": scenario.get("procedures", []),
            }

            try:
                # Обновляем сценарий в базе
                result = await update_users_scenario(
                    scenario_id, {"scenarios": data_to_update}, table_name
                )
                # Проверяем результат
                if result.get("status") == "success":
                    return {"status": "success", "code": 0}
                else:
                    logger.error("Ошибка при обновлении сценария")
                    return {"status": "error", "message": "Failed to update scenario"}
            except Exception as e:
                logger.error(f"Ошибка при запросе к базе данных: {e}")
                return {"status": "error", "message": str(e)}

    # Если сценарий не найден
    logger.error("Сценарий не найден")
    return {"status": "error", "message": "Scenario not found"}


async def delete_previous_messages(bot, chat_id, data, exclude_prompt=False):
    message_ids = data.get("previous_message_ids", [])
    if exclude_prompt:
        prompt_message_id = data.get("prompt_message_id")
        message_ids = [msg_id for msg_id in message_ids if msg_id != prompt_message_id]

    for message_id in message_ids:
        try:
            await bot.delete_message(chat_id, message_id)
        except Exception as e:
            logger.exception(f"Ошибка при удалении сообщения {message_id}: {e}")


def format_patient_info(patient_info):
    stage = patient_info["stage"]
    name_stage = stage_number_to_name[stage]
    response_message = (
        f"Имя пациента: {patient_info['patient_name']} \n"
        f"Номер телефона пациента: {patient_info['patient_phone']}\n"
        f"Этап лечения пациента: {name_stage}\n"
    )
    if "doctor_name" in patient_info and patient_info["doctor_name"]:
        response_message += f"Имя врача: {patient_info['doctor_name']}\n"
    return response_message


async def find_information(message, state, info, by_what):
    all_patients = await get_info_patient_number_surname(info, by_what)
    if all_patients is not None:
        information = all_patients["result"]["items"]
        if len(information) > 1:
            await message.answer(
                "Какой именно пациент вас интересует?",
                reply_markup=kb.inline_patients_keyboard(all_patients, "surname"),
            )
            await state.set_state(AdminStates_find.doctor_name_second)
            return all_patients
        else:
            patient_info = information[0]
            response_message = format_patient_info(patient_info)

            await message.answer("Вот что я сумел найти: ")
            await message.answer(response_message)
            await message.answer(
                "Что ещё хотите сделать?", reply_markup=kb.find_admin_kb()
            )
            await state.set_state(AdminStates_global.find_patient)
    else:
        if by_what == "phone_number":
            await message.answer(
                "К сожалению произошла ошибка. Возможно я не смог найти какие-то данные. Попробуйте снова ввести "
                "номер телефона"
            )
            await state.set_state(AdminStates_find.telephone)
        else:
            await message.answer(
                "К сожалению произошла ошибка. Возможно я не смог найти какие-то данные. Попробуйте снова ввести "
                "фамилию"
            )
            await state.set_state(AdminStates_find.surname)
