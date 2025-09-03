from aiogram.types import URLInputFile

import keyboards.admin_kb as kb
import keyboards.constants as kc
from configuration.config_db import SessionLocal
from sqlalchemy.future import select

from database.admin_send_db import get_general_scenarios
from database.admin_send_db import find_id_doctor
from database.db_helpers import get_url
from database.models import Client
from database.auth_db import replace_content

from database.constants_db import stage_number_to_name
from aiogram.fsm.storage.base import StorageKey

from handlers.admin_general import back_to
from handlers.functions.admins_fun import format_scenarios
from handlers.patient import switch_survey
from scheduler.sched_tasks import split_message_to_two_parts

from states.states_admin import SendScenarioStates

import logging


from configuration.config_bot import dp

import re
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

logger = logging.getLogger(__name__)


def replace_placeholders(content, first_name, last_name):
    """
    Заменяет плейсхолдеры {first_name} и {last_name} в тексте на соответствующие значения.

    :param content: Исходный текст сообщения.
    :param first_name: Имя клиента.
    :param last_name: Фамилия клиента.
    :return: Обновленный текст с подставленными значениями.
    """
    content = content.replace("{first_name}", first_name).replace(
        "{last_name}", last_name
    )
    content = content.replace("/n", "\n")

    return content


async def send_message_list(message: Message, state: FSMContext):
    """
    Отправляет список сообщений пользователю, запрашивает номер сообщения для отправки.

    :param message: Объект сообщения от пользователя.
    :param state: Контекст конечного автомата состояний.
    """
    data = await state.get_data()
    messages = data.get("messages", [])
    first_name = data.get("first_name", "")
    last_name = data.get("last_name", "")

    if not messages:
        await message.answer("В данном сценарии нет сообщений.")
        return

    updated_messages = []
    for msg in messages:
        updated_message = await replace_content(None, msg, first_name, None, last_name)
        updated_messages.append(updated_message)

    await format_scenarios(message.chat.id, "", [{"messages": updated_messages}])

    await message.answer(
        "Введите номер сообщения для отправки:",
        reply_markup=kb.back_to_scenarios_kb(),
    )


async def process_phone_number(message: Message, state: FSMContext):
    """
    Обрабатывает ввод номера телефона, проверяет его корректность и ищет соответствующего клиента в БД.

    :param message: Объект сообщения от пользователя.
    :param state: Контекст конечного автомата состояний.
    """
    if message.text == kc.buttons_admin_back["back"]:
        await back_to(message, state)
        return

    phone_number = message.text

    if (
        not phone_number.startswith("+7")
        or len(phone_number) != 12
        or not phone_number[1:].isdigit()
    ):
        await message.answer(
            "Неверный формат номера телефона. Пожалуйста, введите номер в формате +7XXXXXXXXXX."
        )
        return
    # удаляем + из номера
    phone_number_cleaned = re.sub(r"\D", "", phone_number)

    try:
        phone_number_int = int(phone_number_cleaned)
        async with SessionLocal() as session:
            client_query = await session.execute(
                select(Client).where(Client.phone_number == phone_number_int)
            )
            client = client_query.scalars().first()

            if not client:
                await message.answer(
                    "Пациент с таким номером телефона не найден. Пожалуйста, введите номер телефона "
                    "авторизованного клиента в формате +7XXXXXXXXXX."
                )
                return

            tg_id = client.tg_id
            stage = client.stage or "Неизвестен"
            name_stage = stage_number_to_name.get(stage, "Неизвестен")
            first_name = client.first_name
            last_name = client.last_name

            # Отправляем сообщение о найденном клиенте и его текущем этапе
            await message.answer(
                f"Клиент найден✅\nКлиент: {first_name} {last_name}\nЭтап клиента: {name_stage}\n\n",
                reply_markup=kb.back_to_messages_kb(),
            )

            scenarios = await get_general_scenarios()
            stage_buttons = kb.general_scenario_choose_keyboard(scenarios)

            await message.answer(
                "Выберите сценарий из которого вы хотите отправить сообщение:",
                reply_markup=stage_buttons,
            )

        # Сохраняем данные клиента в состоянии
        await state.update_data(tg_id=tg_id, first_name=first_name, last_name=last_name)
        await state.set_state(SendScenarioStates.waiting_for_stage)

    except Exception as e:
        logger.exception(f"Ошибка при обработке номера телефона: {e}")
        await message.answer(
            "Произошла ошибка при обработке номера телефона. Попробуйте снова.",
            reply_markup=kb.back_to_messages_kb(),
        )


async def process_message_number(message: Message, state: FSMContext, id):
    """
    Обрабатывает выбор номера сообщения и отправляет соответствующее сообщение пользователю.

    :param message: Объект сообщения от пользователя.
    :param state: Контекст конечного автомата состояний.
    :param id: Уникальный идентификатор отправки.
    """
    if message.text == kc.buttons_back["back_to"]:
        scenarios = await get_general_scenarios()
        stage_buttons = kb.general_scenario_choose_keyboard(scenarios)

        await message.answer(
            "Выберите сценарий из которого вы хотите отправить сообщение:",
            reply_markup=stage_buttons,
        )
        await state.set_state(SendScenarioStates.waiting_for_stage)
        return

    if not message.text.isdigit():
        await message.answer(
            "Неверный формат номера сообщения. Пожалуйста, введите корректный номер сообщения."
        )
        return

    message_number = int(message.text)
    data = await state.get_data()
    messages = data.get("messages", [])
    tg_id = data.get("tg_id")
    bot = message.bot
    first_name = data.get("first_name", "")
    last_name = data.get("last_name", "")

    if not (message.text.isdigit() and 1 <= message_number <= len(messages)):
        await message.answer(
            "Сообщение с указанным номером не существует. Пожалуйста, введите корректный номер сообщения."
        )
        return

    message_to_send = messages[message_number - 1]
    content = replace_placeholders(
        message_to_send.get("content", ""), first_name, last_name
    ).replace("/n", "\n")

    max_message_length = 4096
    max_caption_length = 1024

    try:
        msg_type = message_to_send.get("type", "")
        match msg_type:
            case "text":
                # Разбиваем сообщение на части, если оно слишком длинное
                parts = split_message_to_two_parts(content, max_message_length)
                for part in parts:
                    await bot.send_message(tg_id, part, parse_mode='HTML')
            case "video":
                video = message_to_send["url"]
                if len(video) == 0:
                    id_doctor = await find_id_doctor(tg_id)
                    format_video = f"{id}.{message_number}.{id_doctor['doctor_id']}"
                    video = URLInputFile(await get_url(format_video))
                    await bot.send_video(tg_id, video)
                if len(content) > max_caption_length:
                    # Обрезаем caption и отправляем оставшийся текст отдельно
                    caption_part = content[:max_caption_length]
                    remaining_content = content[max_caption_length:]
                    await bot.send_video(tg_id, video, caption=caption_part)
                    await bot.send_message(tg_id, remaining_content, parse_mode='HTML')
                else:
                    await bot.send_video(tg_id, video, caption=content, parse_mode='HTML')
            case "link":
                await bot.send_message(tg_id, message_to_send["url"], parse_mode='HTML')
            case "photo":
                photo = message_to_send["url"]
                if len(content) > max_caption_length:
                    # Обрезаем caption и отправляем оставшийся текст отдельно
                    caption_part = content[:max_caption_length]
                    remaining_content = content[max_caption_length:]
                    await bot.send_photo(tg_id, photo, caption=caption_part, parse_mode='HTML')
                    await bot.send_message(tg_id, remaining_content, parse_mode='HTML')
                else:
                    await bot.send_photo(tg_id, photo, caption=content, parse_mode='HTML')
            case "text link":
                if len(content) > max_caption_length:
                    # Обрезаем caption и отправляем оставшийся текст отдельно
                    caption_part = content[:max_caption_length]
                    remaining_content = content[max_caption_length:]
                    await bot.send_message(
                        tg_id, f'{caption_part}\n{message_to_send["url"]}', parse_mode='HTML'
                    )
                    await bot.send_message(tg_id, remaining_content, parse_mode='HTML')
                else:
                    await bot.send_message(
                        tg_id, f'{content}\n{message_to_send["url"]}', parse_mode='HTML'
                    )
            case "survey":
                id_survey = message_to_send.get("id_survey")
                state_with = FSMContext(
                    storage=dp.storage,
                    key=StorageKey(chat_id=tg_id, user_id=tg_id, bot_id=bot.id),
                )
                await switch_survey(state_with, tg_id, id_survey)
            case _:
                await message.answer(
                    "Неизвестный тип сообщения. Пожалуйста, выберите правильное сообщение."
                )

        await message.answer("Сообщение успешно отправлено!")

        keyboard = kb.yes_no_keyboard()
        await message.answer("Отправить ещё сообщения?", reply_markup=keyboard)
        await state.set_state(SendScenarioStates.waiting_for_more_messages)

    except Exception as e:
        logger.exception(f"Ошибка при отправке сообщения: {e}")
        await message.answer(
            "Произошла ошибка при отправке сообщения. Попробуйте отправить другое сообщение.",
            reply_markup=kb.back_to_messages_kb(),
        )
        await state.set_state(SendScenarioStates.waiting_for_message_number)
