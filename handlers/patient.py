import logging
import os
import asyncio

from aiogram import types, Router, F

from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, ReplyKeyboardRemove, URLInputFile
from aiogram.enums import ChatType
from dotenv import load_dotenv

from configuration.config_bot import bot

import keyboards.patient_kb as kb
import keyboards.constants as kc
from database.admin_send_db import find_id_doctor
from database.db_helpers import get_url
from database.questions_db import (
    update_question_response,
    has_unanswered_question,
    is_question_answered,
    cancel_question_in_db,
    get_patient_name_by_tg_id,
)
from database.survey_db import (
    add_to_result_in_survey,
    get_survey_by_id,
    get_client_name_by_tg_id,
    get_doctor_by_client_tg_id,
    add_survey_answers,
)
from states.states_patient import PatientStates
from handlers.functions.patient_ask import (
    send_question_to_support,
    extract_question_id_from_message,
    get_patient_tg_id_from_question_id,
    support_group_id,
)
from middlewares.middlewares import TestMiddleware
from configuration.config_db import SessionLocal
from database.schedule import get_schedule_by_tg_id

from database.constants_db import preparations, stage_number_to_name


patient_router = Router()
patient_tg_id = 0

load_dotenv()
send_lock = asyncio.Lock()
patient_router.message.middleware(TestMiddleware())
logger = logging.getLogger(__name__)
choose_action = "Выберите действие"
support_group_id = os.getenv("SUPPORT_GROUP_ID")


@patient_router.message(Command("patient"))
async def handle_patient_command(message: types.Message, state: FSMContext):
    global patient_tg_id
    user_data = await state.get_data()
    tg_id = user_data.get("tg_id")

    patient_tg_id = tg_id
    await message.bot.send_message(
        tg_id,
        text="Выберите действие в меню:",
        reply_markup=kb.patient_menu_keyboard(),
    )
    await state.set_state(PatientStates.menu)


async def send_schedule_info(message: types.Message, patient_tg_id: int):
    """
    Отправляет пользователю информацию о его ближайшей записи.

    :param message: Объект сообщения от пользователя.
    :param patient_tg_id: Telegram ID клиента, для которого нужно найти расписание.
    :return: None. Отправляет сообщение с данными о записи или уведомление об отсутствии записей.
    """

    async with SessionLocal() as session:
        schedule = await get_schedule_by_tg_id(patient_tg_id, session)
        if schedule["result"]["code"] == 0:
            schedule = schedule["result"]["item"]
            await message.answer("Найдена запись ✨")

            # преобразуем в нужный формат
            start_time = schedule["start_time"]
            date = start_time.strftime("%Y-%m-%d")
            time = start_time.strftime("%H:%M")

            name_procedure = schedule["procedure_name"]
            doctor = schedule["doctor_last_name"] + " " + schedule["doctor_first_name"] + " " + schedule["doctor_middle_name"]

            await message.answer(
                f"<b>{date}</b> в <b>{time}</b>\nНа процедуру: <b>{name_procedure}</b>\n"
                f"У доктора: <b>{doctor}</b>",
                parse_mode="HTML",
            )
        else:
            await message.answer("Запись не найдена 🙈")


@patient_router.message(
    PatientStates.menu, F.text == kc.buttons_patient_menu["schedule"]
)
async def menu_handler(message: types.Message, state: FSMContext):
    """Обрабатывает запрос на получение расписания и отправляет информацию о расписании пациенту."""
    await send_schedule_info(message, message.from_user.id)
    await state.set_state(PatientStates.menu)


@patient_router.message(
    PatientStates.menu, F.text == kc.buttons_patient_menu["question"]
)
async def question_handler(message: types.Message, state: FSMContext):
    """Обрабатывает запрос на отправку вопроса в поддержку, проверяет наличие неотвеченных вопросов."""
    user_id = message.from_user.id

    async with SessionLocal() as db_session:
        # проверяем наличие неотвеченных вопросов
        if await has_unanswered_question(user_id, db_session):
            await message.answer(
                "Ваш вопрос уже был отправлен в поддержку. Пожалуйста, дождитесь ответа."
            )
        else:
            await message.answer(
                "Задайте свой вопрос, который отправится в поддержку: ",
                reply_markup=kb.patient_question_keyboard(),
            )
            await state.set_state(PatientStates.ask_question)


@patient_router.message(PatientStates.ask_question)
async def answer_question_handler(message: types.Message, state: FSMContext):
    """Обрабатывает введенный вопрос от пациента и отправляет его в поддержку, либо возвращает в меню."""
    # Проверка, является ли сообщение текстовым
    if message.content_type != "text":
        await message.answer(
            "Неверный формат вопроса. Пожалуйста, введите только текст вопроса.",
            reply_markup=kb.patient_question_keyboard(),  # Клавиатура с кнопкой для возврата в меню
        )
        return

    # Проверка, если пользователь решил вернуться в меню
    if message.text == kc.buttons_patient_question["back"]:
        await message.answer(choose_action, reply_markup=kb.patient_menu_keyboard())
        await state.set_state(PatientStates.menu)
    else:
        # Отправляем вопрос поддержке
        await send_question_to_support(message, state)
        await message.answer(
            "Что вы хотите сделать дальше?",
            reply_markup=kb.patient_question_cancel_keyboard(),
        )
        await state.set_state(PatientStates.awaiting_response)


@patient_router.message(PatientStates.awaiting_response)
async def handle_cancel_or_schedule(message: types.Message, state: FSMContext):
    """Обрабатывает запрос на отмену вопроса или получение расписания во время ожидания ответа от поддержки."""
    data = await state.get_data()
    question_id = data.get("question_id")

    async with SessionLocal() as db_session:
        if message.text == kc.buttons_patient_cancel["cancel_question"]:
            # Отмена вопроса
            response = await cancel_question_in_db(question_id, db_session)

            if response:
                patient_name = await get_patient_name_by_tg_id(
                    message.from_user.id, db_session
                )
                first_name = patient_name["first_name"] if patient_name else "Без имени"
                last_name = patient_name["last_name"] if patient_name else ""

                # Обновляем текст вопроса в группе поддержки
                support_msg_id = data.get("support_msg_id")
                if support_msg_id:
                    await message.bot.edit_message_text(
                        text=(
                            f"Вопрос №{question_id}.\n\n"
                            f"Пациент: {first_name} {last_name}\n"
                            f"Статус вопроса: отменен🗑️"
                        ),
                        chat_id=support_group_id,
                        message_id=support_msg_id,
                        parse_mode="HTML",
                    )
                await message.answer("Ваш вопрос был отменен.")
            else:
                await message.answer(
                    "Произошла ошибка при отмене вопроса. Пожалуйста, попробуйте снова."
                )

            await message.answer(choose_action, reply_markup=kb.patient_menu_keyboard())
            await state.set_state(PatientStates.menu)
            return  # Возврат для предотвращения дальнейшего выполнения кода
        elif message.text == kc.buttons_patient_cancel["schedule"]:
            await send_schedule_info(message, message.from_user.id)
        elif message.text == kc.buttons_patient_menu["question"]:
            await message.answer(
                "Задайте свой вопрос, который отправится в поддержку: ",
                reply_markup=kb.patient_question_keyboard(),
            )
            await state.set_state(PatientStates.ask_question)


@patient_router.message(
    lambda message: message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]
)
async def handle_support_message(message: types.Message, state: FSMContext):
    """Обрабатывает сообщения в поддержке, отвечает на вопросы пациентов и обновляет статус вопросов."""
    try:
        if message.reply_to_message:
            original_message = message.reply_to_message
            question_id = extract_question_id_from_message(original_message.text)

            async with SessionLocal() as db_session:
                # Проверяем статус вопроса
                status = await is_question_answered(question_id, db_session)

                if status is None:
                    logger.error("Произошла ошибка при проверке статуса вопроса.")
                    return

                if status:
                    if original_message.text.find("отменен🗑️") != -1:
                        await message.reply("Этот вопрос был отменен.")
                    else:
                        await message.reply("Вы уже ответили на данный вопрос.")
                    return

                support_response = message.text.strip()
                patient_tg_id = await get_patient_tg_id_from_question_id(
                    question_id, db_session
                )

                if patient_tg_id is None:
                    await message.reply("Не удалось найти пациента для ответа.")
                    return

                response = await update_question_response(
                    question_id, support_response, db_session
                )

                if response:
                    # обновляем текст вопроса в чате поддержки
                    chat_id = message.chat.id
                    message_id = original_message.message_id
                    original_text = original_message.text

                    updated_text = original_text.replace("открыт✅", "закрыт❌")
                    await message.bot.edit_message_text(
                        text=updated_text,
                        chat_id=chat_id,
                        message_id=message_id,
                        parse_mode="HTML",
                    )

                    try:
                        await message.bot.send_message(
                            patient_tg_id,
                            f"Поддержка ответила на ваш вопрос.\nОтвет:\n{support_response}",
                            parse_mode="HTML",
                            reply_markup=kb.patient_menu_keyboard(),
                        )
                    except Exception as e:
                        logger.exception(f"Ошибка в отправке сообщения пациенту: {e}")

                    await state.set_state(PatientStates.menu)
                    await message.reply("Ответ успешно отправлен пациенту.")
                else:
                    await message.reply(
                        "Произошла ошибка при отправке ответа пациенту. Пожалуйста, попробуйте снова."
                    )

    except ValueError as e:
        logger.exception(f"Ошибка: {e}")


async def survey_info(state: FSMContext, chat_id):
    global patient_tg_id
    if patient_tg_id is None:
        user_data = await state.get_data()
        patient_tg_id = user_data.get("tg_id")

    await bot.send_message(
        chat_id=chat_id,
        text="Пожалуйста напишите ответ текстом и отправьте или выберите ответ в меню:",
        reply_markup=kb.no_question_keyboard(),
    )
    await bot.send_message(
        chat_id=chat_id,
        text="Какой информации Вам не хватает в данный момент о предстоящей программе лечения? Есть ли у Вас какие-либо вопросы или беспокойства?",
    )
    await state.set_state(PatientStates.info_survey)


@patient_router.message(PatientStates.info_survey)
async def send_to_doctor(message: types.Message, state: FSMContext):

    data = {
        "title": "Какой информации Вам не хватает в данный момент о предстоящей программе лечения?",
        "answers": [],
    }
    if message.text != kc.buttons_patient_no_question["no question"]:
        send_message = message.text
        data["answers"].append(
            {
                "question": "Тревожат ли Вас какие-то вопросы?",
                "answer": f"{send_message}",
            }
        )
        await send_bad_answers_to_doctor(data)
        await add_to_result_in_survey(patient_tg_id, "Bad")
    else:
        await send_positive_answers_to_doctor(data)
        await add_to_result_in_survey(patient_tg_id, "Good")
    await message.answer(
        "Большое спасибо за участие в опросе❤️", reply_markup=kb.patient_menu_keyboard()
    )
    await state.set_state(PatientStates.menu)


async def survey_with_answers(state: FSMContext, chat_id, survey_id):
    all_survey = await get_survey_by_id(survey_id)
    survey = all_survey["result"]["file"]
    description = survey["description"]
    title = survey["title"]

    await state.update_data(
        survey=survey,
        current_question_index=0,
        point=0,
        title=title,
        bad_answers={"title": title, "answers": []},
    )

    await bot.send_message(
        chat_id=chat_id, text=description, reply_markup=ReplyKeyboardRemove()
    )
    await ask_next_question(state, None, chat_id=chat_id)


async def ask_next_question(
    state: FSMContext,
    message_or_query: types.Message | types.CallbackQuery | None = None,
    chat_id: int | None = None,
):
    data = await state.get_data()
    questions = data["survey"]["questions"]
    current_question_index = data["current_question_index"]

    if current_question_index < len(questions):
        question = questions[current_question_index]
        await state.set_state(PatientStates.ask_survey)
        if isinstance(message_or_query, types.Message):
            await message_or_query.answer(
                text=f"{question['question_text']}",
                reply_markup=await kb.inline_survey(question["answers"]),
            )
        elif isinstance(message_or_query, types.CallbackQuery):
            await message_or_query.message.edit_text(
                text=f"{question['question_text']}",
                reply_markup=await kb.inline_survey(question["answers"]),
            )
        elif chat_id:
            await bot.send_message(
                chat_id=chat_id,
                text=f"{question['question_text']}",
                reply_markup=await kb.inline_survey(question["answers"]),
            )
    else:
        await message_or_query.message.delete()

        total_points = data["point"]
        if total_points < 0:
            await add_to_result_in_survey(patient_tg_id, "Bad")
            bad_answers = data.get("bad_answers", {})
            await send_bad_answers_to_doctor(bad_answers)
        elif total_points == 0:
            await add_to_result_in_survey(patient_tg_id, "Normal")
            await send_positive_answers_to_doctor(data)

        else:
            await add_to_result_in_survey(patient_tg_id, "Good")
            await send_positive_answers_to_doctor(data)

        await message_or_query.message.answer("Спасибо за участие в опросе ❤️")
        await message_or_query.message.answer(
            "Выберите действие в меню: ", reply_markup=kb.patient_menu_keyboard()
        )
        await state.set_state(PatientStates.menu)


@patient_router.callback_query(PatientStates.ask_survey)
async def test_survey_ask(query: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    current_point = data["point"]
    current_question_index = data["current_question_index"]
    questions = data["survey"]["questions"]
    question = questions[current_question_index]

    point = question["answers"][query.data]["point"]

    new_point = current_point + point

    # Извлекаем текст кнопки, которая была нажата
    button_text = question["answers"][query.data]["text"]

    if point < 0:
        # Добавляем в список плохих ответов
        bad_answers = data.get("bad_answers", {})
        bad_answers["answers"].append(
            {"question": question["question_text"], "answer": button_text}
        )
        await state.update_data(bad_answers=bad_answers)

    await state.update_data(
        point=new_point, current_question_index=current_question_index + 1
    )

    await ask_next_question(state, query)


async def survey_preparation(state: FSMContext, chat_id):
    await bot.send_message(
        chat_id=chat_id,
        text="Пожалуйста, выберите препарат, который назначил вам врач",
        reply_markup=ReplyKeyboardRemove(),
    )
    await bot.send_message(
        chat_id=chat_id,
        text="Список препаратов:",
        reply_markup=await kb.inline_preparations(preparations),
    )
    await state.update_data(chat_id=chat_id)
    await state.set_state(PatientStates.survey_preparation)


@patient_router.callback_query(PatientStates.survey_preparation)
async def send_video(query: CallbackQuery, state: FSMContext):

    state_data = await state.get_data()
    chat_id = state_data["chat_id"]

    await query.message.delete()
    format_preparation = f"3.3.{int(query.data)}"
    video_url = await get_url(format_preparation)
    processing_message = await bot.send_message(
        chat_id=chat_id, text="Отправляю видео..."
    )
    await bot.send_video(
        chat_id=chat_id,
        video=video_url,
        caption="Пожалуйста, просмотрите данное видео",
        supports_streaming=True,
    )
    async with send_lock:
        await bot.delete_message(
            chat_id=chat_id, message_id=processing_message.message_id
        )
        # Здесь будет отправка видео из хранилища
        await bot.send_message(
            chat_id=chat_id,
            text="Выберите действие в меню: ",
            reply_markup=kb.patient_menu_keyboard(),
        )
        await state.set_state(PatientStates.menu)


async def survey_injection(state: FSMContext, chat_id):
    title = "Вам удалось поставить укол?"
    await bot.send_message(
        chat_id=chat_id,
        text="Вам удалось поставить укол?",
        reply_markup=kb.yes_or_no(),
    )
    await state.update_data(
        title=title,
        bad_answers={"title": title, "answers": []},
    )
    await state.set_state(PatientStates.survey_injection)


@patient_router.message(
    PatientStates.survey_injection, F.text == kc.buttons_patient_yes_or_no["yes"]
)
async def after_injection_answer_yes(message: types.Message, state: FSMContext):
    data = await state.get_data()
    await send_positive_answers_to_doctor(data)
    await add_to_result_in_survey(patient_tg_id, "Good")
    await message.answer("Спасибо за участие в опросе ❤️")
    await message.answer(
        "Выберите действие в меню: ", reply_markup=kb.patient_menu_keyboard()
    )
    await state.set_state(PatientStates.menu)


@patient_router.message(
    PatientStates.survey_injection, F.text == kc.buttons_patient_yes_or_no["no"]
)
async def after_injection_answer_no(message: types.Message, state: FSMContext):
    await message.answer(
        "Какие проблемы возникли с постановкой укола?",
        reply_markup=ReplyKeyboardRemove(),
    )
    await state.set_state(PatientStates.no_injection_reason)


@patient_router.message(PatientStates.no_injection_reason)
async def send_to_doctor_reason(message: types.Message, state: FSMContext):
    # Здесь будет отправка причины врачу
    data = await state.get_data()
    bad_answers = data.get("bad_answers", {})
    bad_answers["answers"].append(
        {"question": "Не удалось, причина", "answer": f"{message.text}"}
    )
    await send_bad_answers_to_doctor(bad_answers)
    await add_to_result_in_survey(patient_tg_id, "Bad")
    await message.answer("Спасибо за участие в опросе ❤️")
    await message.answer(
        "Выберите действие в меню: ", reply_markup=kb.patient_menu_keyboard()
    )
    await state.set_state(PatientStates.menu)


# Опрос про эмоциональное состояние
async def survey_emotion(state: FSMContext, chat_id, survey_id):
    survey_all = await get_survey_by_id(survey_id)
    survey = survey_all["result"]["file"]
    description = survey["description"]
    title = survey["title"]

    part1_questions = survey["parts"]["part1"]["questions"]
    part2_questions = survey["parts"]["part2"]["questions"]
    all_questions = (
        part1_questions + part2_questions
    )  # Объединяем вопросы в один список

    await state.update_data(
        survey=survey,
        all_questions=all_questions,
        part1_count=len(part1_questions),
        part2_count=len(part2_questions),
        current_question_index=0,
        point_part1=0,  # Очки для первой части
        point_part2=0,  # Очки для второй части
        title=title,
        bad_answers={"title": title, "answers": []},
    )

    await bot.send_message(
        chat_id=chat_id, text=description, reply_markup=ReplyKeyboardRemove()
    )
    await ask_next_question_emotion(state, chat_id=chat_id)


async def ask_next_question_emotion(
    state: FSMContext,
    message_or_query: types.Message | types.CallbackQuery | None = None,
    chat_id: int | None = None,
):
    data = await state.get_data()
    current_question_index = data["current_question_index"]
    all_questions = data["all_questions"]

    # Если индекс превысил или равен количеству вопросов - завершаем
    if current_question_index >= len(all_questions):
        if isinstance(message_or_query, types.CallbackQuery):
            await finish_survey(state, message_or_query)
        elif isinstance(message_or_query, types.Message):
            await finish_survey(state, message_or_query)
        elif chat_id:
            # Если вдруг не через колбэк и не через сообщение, можно отправить финал куда нужно
            # Но в реальности вы скорее всего вызываете эту функцию из колбэка или сообщения
            pass
        return

    question = all_questions[current_question_index]

    await state.set_state(PatientStates.ask_survey_emotion)

    if isinstance(message_or_query, types.Message):
        await message_or_query.answer(
            text=question["question_text"],
            reply_markup=await kb.inline_survey(question["answers"]),
        )
    elif isinstance(message_or_query, types.CallbackQuery):
        await message_or_query.message.edit_text(
            text=question["question_text"],
            reply_markup=await kb.inline_survey(question["answers"]),
        )
    elif chat_id:
        await bot.send_message(
            chat_id=chat_id,
            text=question["question_text"],
            reply_markup=await kb.inline_survey(question["answers"]),
        )


@patient_router.callback_query(PatientStates.ask_survey_emotion)
async def emotion_survey_ask(query: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    current_question_index = data["current_question_index"]
    all_questions = data["all_questions"]
    part1_count = data["part1_count"]
    part2_count = data["part2_count"]

    # Получаем текущий вопрос
    question = all_questions[current_question_index]

    # Получаем балл из ответа
    point = question["answers"][query.data]["point"]

    # Определяем, к какой части относится вопрос
    if current_question_index < part1_count:
        # Вопрос из первой части
        point_part1 = data.get("point_part1", 0) + point
        await state.update_data(point_part1=point_part1)
    else:
        # Вопрос из второй части
        point_part2 = data.get("point_part2", 0) + point
        await state.update_data(point_part2=point_part2)

    # Увеличиваем индекс вопроса
    new_index = current_question_index + 1
    await state.update_data(current_question_index=new_index)

    # Проверяем, не закончились ли все вопросы
    if new_index >= len(all_questions):
        # Все вопросы заданы, завершаем опрос
        await finish_survey(state, query)
    else:
        # Продолжаем опрос
        await ask_next_question_emotion(state, query)


async def finish_survey(
    state: FSMContext, message_or_query: types.CallbackQuery | types.Message
):
    data = await state.get_data()
    point_part1 = data["point_part1"]
    point_part2 = data["point_part2"]
    bad_answers = data.get("bad_answers", {})

    survey_result = "Good"

    # Проверяем показатели
    if point_part1 > 7:
        bad_answers["answers"].append(
            {"question": "Тревожность", "answer": "Тревожность присутствует"}
        )
    if point_part2 > 7:
        bad_answers["answers"].append(
            {"question": "Депрессия", "answer": "Депрессия присутствует"}
        )

    if point_part1 > 7 or point_part2 > 7:
        survey_result = "Bad"
        await send_bad_answers_to_doctor(bad_answers)

        await bot.send_message(
            text="Вы находитесь в состоянии повышенной тревожности. Для нормализации эмоционального фона в программе ЭКО предусмотрена консультация репродуктивного психолога. На приёме Вы сможете поработать с тревогами и стрессом перед предстоящим лечением. При следующем визите в клинику узнайте у врача или у администраторов на ресепшн о ближайшем доступном времени для консультации с психологом. Ваш психологический комфорт также важен, как и состояние тела.",
            chat_id=patient_tg_id,
        )

    else:
        await send_positive_answers_to_doctor(data)

        await bot.send_message(
            text="Ваше психоэмоциональное состояние в норме! Однако, если Вы чувствуете необходимость в поддержке, у Вас есть возможность в рамках программы ЭКО посетить консультацию репродуктивного психолога. На приёме Вы сможете поработать с возможными тревогами и стрессом. Узнайте у лечащего врача или у администраторов на ресепшн о ближайшем возможном времени консультации. Не упускайте возможность проработать эмоциональные аспекты лечебного процесса.",
            chat_id=patient_tg_id,
        )

    await add_to_result_in_survey(patient_tg_id, survey_result)

    # Ответ пользователю
    if isinstance(message_or_query, types.CallbackQuery):
        await message_or_query.message.delete()
        await message_or_query.message.answer("Спасибо за участие в опросе ❤️")
        await message_or_query.message.answer(
            "Выберите действие в меню: ", reply_markup=kb.patient_menu_keyboard()
        )
    elif isinstance(message_or_query, types.Message):
        await message_or_query.answer("Спасибо за участие в опросе ❤️")
        await message_or_query.answer(
            "Выберите действие в меню: ", reply_markup=kb.patient_menu_keyboard()
        )

    await state.set_state(PatientStates.menu)


@patient_router.callback_query(PatientStates.ask_survey_emotion)
async def emotion_survey_ask(query: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    current_question_index = data["current_question_index"]

    part1_questions = data["survey"]["parts"]["part1"]["questions"]
    part2_questions = data["survey"]["parts"]["part2"]["questions"]
    total_part1 = len(part1_questions)
    total_part2 = len(part2_questions)
    total_questions = total_part1 + total_part2

    # Определяем, к какой части относится текущий вопрос
    if current_question_index < total_part1:
        question = part1_questions[current_question_index]
        is_first_part = True
    else:
        is_first_part = False
        question_index_in_part2 = current_question_index - total_part1
        question = part2_questions[question_index_in_part2]

    # Получаем балл из ответа
    point = question["answers"][query.data]["point"]

    # Обновляем баллы
    if is_first_part:
        point_part1 = data.get("point_part1", 0) + point
        await state.update_data(point_part1=point_part1)
    else:
        point_part2 = data.get("point_part2", 0) + point
        await state.update_data(point_part2=point_part2)

    # Увеличиваем индекс текущего вопроса
    new_index = current_question_index + 1
    await state.update_data(current_question_index=new_index)

    # Проверяем, не закончились ли все вопросы
    if new_index >= total_questions:
        # Все вопросы заданы, завершаем опрос
        await finish_survey(state, query)
    else:
        # Продолжаем опрос
        await ask_next_question_emotion(state, query)


async def survey_not_record(state: FSMContext, chat_id):
    await bot.send_message(
        chat_id=chat_id,
        text="Вам удалось записаться на консультацию по ведению беременности?",
        reply_markup=kb.yes_or_no(),
    )

    await state.set_state(PatientStates.survey_not_record)


@patient_router.message(
    PatientStates.survey_not_record, F.text == kc.buttons_patient_yes_or_no["yes"]
)
async def survey_not_record_yes(message: types.Message, state: FSMContext):
    await message.answer("Спасибо за участие в опросе ❤️")
    await message.answer(
        "Выберите действие в меню: ", reply_markup=kb.patient_menu_keyboard()
    )
    await state.set_state(PatientStates.menu)


@patient_router.message(
    PatientStates.survey_not_record, F.text == kc.buttons_patient_yes_or_no["no"]
)
async def survey_not_record_no(message: types.Message, state: FSMContext):
    patient_tg_id = message.from_user.id

    if not patient_tg_id:
        logger.error("Ошибка: не удалось получить идентификатор пациента.")
        return

    full_info = await bot.get_chat(patient_tg_id)

    patient_info = await get_client_name_by_tg_id(patient_tg_id)
    first_name = patient_info["result"]["first_name"]
    last_name = patient_info["result"]["last_name"]
    phone_number = patient_info["result"]["phone_number"]
    username = full_info.username if full_info else "Неизвестно"
    stage = stage_number_to_name.get(patient_info["result"]["stage"], "Неизвестно")

    out_text = (
        f"<b>Пациент</b>: {first_name} {last_name}\n<b>Телефон</b>: +{phone_number}\n"
        f"<b>Аккаунт</b>: @{username}\n<b>Текущий сценарий</b>: {stage}\n\n"
        f"<b>Результат опроса</b>: Не смог записаться на консультацию по ведению беременности"
    )

    # отправляем сообщение в поддержку
    await send_to_call_center(out_text)

    await message.answer(
        "Спасибо за участие в опросе ❤️\nС Вами свяжется координатор и подберет удобное время. Желаем прекрасного дня!"
    )
    await message.answer(
        "Выберите действие в меню: ", reply_markup=kb.patient_menu_keyboard()
    )
    await state.set_state(PatientStates.menu)


async def survey_all_good(state: FSMContext, chat_id):
    await bot.send_message(
        chat_id=chat_id,
        text="Все ли у вас хорошо?",
        reply_markup=kb.yes_or_no(),
    )

    await state.set_state(PatientStates.survey_all_good)


@patient_router.message(
    PatientStates.survey_all_good, F.text == kc.buttons_patient_yes_or_no["yes"]
)
async def survey_all_good_yes(message: types.Message, state: FSMContext):
    await message.answer(
        "Вся наша команда с нетерпением будет ждать от Вас сообщение после родов!"
        " Напишите, пожалуйста, своему лечащему врачу информацию после рождения малыша ❤️"
    )
    await message.answer(
        "Выберите действие в меню: ", reply_markup=kb.patient_menu_keyboard()
    )
    await state.set_state(PatientStates.menu)


@patient_router.message(
    PatientStates.survey_all_good, F.text == kc.buttons_patient_yes_or_no["no"]
)
async def survey_all_good_no(message: types.Message, state: FSMContext):

    await message.answer(
        "Вам помочь записаться к врачу-репродуктологу для составления дальнейших планов?",
        reply_markup=kb.yes_or_no(),
    )
    await state.set_state(PatientStates.survey_all_good_need_help)


@patient_router.message(
    PatientStates.survey_all_good_need_help,
    F.text == kc.buttons_patient_yes_or_no["no"],
)
async def survey_all_good_no_no(message: types.Message, state: FSMContext):

    await message.answer(
        "Спасибо за участие в опросе ❤️", reply_markup=kb.patient_menu_keyboard()
    )
    await state.set_state(PatientStates.menu)


@patient_router.message(
    PatientStates.survey_all_good_need_help,
    F.text == kc.buttons_patient_yes_or_no["yes"],
)
async def survey_all_good_no_yes(message: types.Message, state: FSMContext):
    patient_tg_id = message.from_user.id

    if not patient_tg_id:
        logger.error("Ошибка: не удалось получить идентификатор пациента.")
        return
    full_info = await bot.get_chat(patient_tg_id)

    patient_info = await get_client_name_by_tg_id(patient_tg_id)
    first_name = patient_info["result"]["first_name"]
    last_name = patient_info["result"]["last_name"]
    phone_number = patient_info["result"]["phone_number"]
    username = full_info.username
    stage = stage_number_to_name[patient_info["result"]["stage"]]

    out_text = (
        f"<b>Пациент</b>: {first_name} {last_name}\n<b>Телефон</b>: +{phone_number}\n"
        f"<b>Аккаунт</b>: @{username}\n<b>Текущий сценарий</b>: {stage}\n\n"
        f"<b>Результат опроса</b>: Запрашивает запись к врачу-репродуктологу после проведенной программы."
    )

    await send_to_call_center(out_text)

    await message.answer(
        "Спасибо за участие в опросе ❤️", reply_markup=kb.patient_menu_keyboard()
    )
    await state.set_state(PatientStates.menu)


# Функции отправки результатов опросов


async def send_bad_answers_to_doctor(data):
    result = {"title": data["title"], "answers": data["answers"]}
    await add_survey_answers(patient_tg_id, result)

    full_info = await bot.get_chat(patient_tg_id)

    doctor_tg_ids_all = await get_doctor_by_client_tg_id(patient_tg_id)
    doctor_tg_ids = doctor_tg_ids_all["result"]["doctors"]

    patient_info = await get_client_name_by_tg_id(patient_tg_id)
    first_name = patient_info["result"]["first_name"]
    last_name = patient_info["result"]["last_name"]
    phone_number = patient_info["result"]["phone_number"]
    username = full_info.username
    stage = stage_number_to_name[patient_info["result"]["stage"]]

    out_text = (
        f"<u>Тревожные ответы</u> ‼️\n\n<b>Пациент</b>: {first_name} {last_name}\n<b>Телефон</b>: +{phone_number}\n"
        f"<b>Аккаунт</b>: @{username}\n<b>Текущий сценарий</b>: {stage}\n\n<b>Опрос</b>: {result['title']}\n\n"
    )
    for answer in result["answers"]:
        out_text += (
            f"<b>Вопрос:</b> {answer['question']}\n<b>Ответ:</b> {answer['answer']}\n\n"
        )
    for doc_id in doctor_tg_ids:
        await bot.send_message(
            text=out_text, chat_id=doc_id["tg_id"], parse_mode="HTML"
        )


async def send_positive_answers_to_doctor(data):
    result = {"title": data["title"]}
    await add_survey_answers(patient_tg_id, result)


async def send_to_call_center(out_text):
    await bot.send_message(chat_id=support_group_id, text=out_text, parse_mode="HTML")


# Функции переключения на нужный опрос
async def switch_survey(state, tg_id, survey_id):
    survey_list = {
        1: "survey_info",
        2: "survey_preparation",
        3: "survey_injection",
        4: "survey_after_procedure",
        5: "survey_emotion",
        6: "survey_not_record",
        7: "survey_all_good",
    }
    out_survey = survey_list[int(survey_id)]
    match out_survey:
        case "survey_info":
            await survey_info(state, tg_id)
        case "survey_preparation":
            await survey_preparation(state, tg_id)
        case "survey_injection":
            await survey_injection(state, tg_id)
        case "survey_after_procedure":
            await survey_with_answers(state, tg_id, 1)
        case "survey_emotion":
            await survey_emotion(state, tg_id, 2)
        case "survey_not_record":
            await survey_not_record(state, tg_id)
        case "survey_all_good":
            await survey_all_good(state, tg_id)


# Команды для отладки
@patient_router.message(Command("survey_info"))
async def func_survey_info(message: types.Message, state: FSMContext):
    await survey_info(state, chat_id=message.chat.id)


@patient_router.message(Command("survey_preparation"))
async def func_survey_info(message: types.Message, state: FSMContext):
    await survey_preparation(state, chat_id=message.chat.id)


@patient_router.message(Command("survey_injection"))
async def func_survey_info(message: types.Message, state: FSMContext):
    await survey_injection(state, chat_id=message.chat.id)


@patient_router.message(Command("survey_after"))
async def func_survey_info(message: types.Message, state: FSMContext):
    await survey_with_answers(state, chat_id=message.chat.id, survey_id=1)


@patient_router.message(Command("survey_emotion"))
async def func_survey_info(message: types.Message, state: FSMContext):
    await survey_emotion(state, chat_id=message.chat.id, survey_id=2)


@patient_router.message(Command("survey_not_record"))
async def func_survey_not_record(message: types.Message, state: FSMContext):
    await survey_not_record(state, chat_id=message.chat.id)


@patient_router.message(Command("survey_all_good"))
async def func_survey_all_good(message: types.Message, state: FSMContext):
    await survey_all_good(state, chat_id=message.chat.id)
