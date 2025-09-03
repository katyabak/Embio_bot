import asyncio
import re

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import ContentType, Message, CallbackQuery
import logging

from configuration.config_bot import bot
from handlers.doctor import handle_auth_doctor
from handlers.functions.auth_crm_fun import (
    get_user_data,
    get_sotr_data,
    authenticate_patient,
    authenticate_doctor,
    validate_phone_number, send_access_request_to_support,
)
from handlers.patient import handle_patient_command
from states.states_auth import AuthStates
from states.states_doctor import DoctorStates
from states.states_patient import PatientStates

from keyboards.auth_kb import get_phone_keyboard, get_approve_keyboard
from states.states_admin import AdminStates_global
from handlers.admin_general import start_admin
from database.auth_db import (
    save_client_data,
    save_doctor_data,
    check_if_admin,
    set_appointments,
    get_null_scenarios,
)

auth_router = Router()
waiting_message = "Обработка запроса, пожалуйста подождите..."
not_correct_manual_phone = "Неверный формат номера телефона. Пожалуйста, введите номер вручную в формате +7XXXXXXXXXX."

logger = logging.getLogger(__name__)
wait_for_accept = "Дождитесь подтверждения. Ваш запрос отправлен в поддержку."
auth_success = "Ваша авторизация подтверждена. Добро пожаловать!"


@auth_router.message(Command("start"))
async def start_command(message: Message, state: FSMContext):
    """ Обрабатывает команду /start, проверяет, является ли пользователь администратором."""
    chat_id = message.chat.id

    # Проверка, является ли пользователь администратором
    admin_check_response = await check_if_admin(chat_id)
    if admin_check_response:
        # если является, его сразу перекидывает в admin без авторизации

        await state.set_state(AdminStates_global.menu)
        await start_admin(message, state)
        return
    keyboard = get_phone_keyboard()
    await message.answer(
        "Добро пожаловать! Я Ассистент ЭмБио, готов помочь на пути лечения :)\nПожалуйста, нажмите кнопку ниже, "
        "чтобы поделиться своим номером телефона.",
        reply_markup=keyboard,
    )
    await state.update_data(tg_id=chat_id)
    await state.set_state(AuthStates.waiting_for_phone)


@auth_router.message(
    AuthStates.waiting_for_phone, F.content_type == ContentType.CONTACT
)
async def process_contact(message: Message, state: FSMContext):
    """Обрабатывает контактный номер телефона, проверяет, существует ли он в CRM, и авторизует пациента или
    доктора."""
    contact = message.contact
    phone = validate_phone_number(contact.phone_number)
    chat_id = message.chat.id
    # проверка, что tg_phone принадлежит клиенту
    if contact.user_id != message.from_user.id:
        await bot.send_message(
            chat_id=chat_id,
            text="Номер телефона не принадлежит вам.\nПожалуйста, отправьте свой собственный номер телефона с "
            "помощью кнопки в меню.",
        )
        return
    processing_msg = await message.answer(waiting_message)
    await state.update_data(tg_id=chat_id)
    try:
        if not phone.startswith("+"):
            phone = f"+{phone}"
        # если tg номер есть в crm у пациента, авторизуем без подтверждения
        response = await get_user_data(phone)
        if response.get("result", {}).get("code") == 0:

            await state.update_data(
                role="patient",
                phone=phone,
                tg_id=chat_id,
            )

            await authenticate_patient(phone, state)
            user = await state.get_data()
            client_id = user["id_crm"]
            await save_client_data(
                chat_id,
                user["name"].split()[1],
                user["name"].split()[0],
                user.get("passport"),
                phone,
                user["id_crm"],
                stage=1,
            )
            await set_appointments(client_id, chat_id)
            scenario_null = await get_null_scenarios(0, user["name"].split()[1])
            welcome_message = scenario_null["messages"][0]
            await processing_msg.delete()
            await bot.send_message(chat_id=chat_id, text=welcome_message["content"])
            await state.set_state(PatientStates.menu)
            await handle_patient_command(message, state)
            return

        # если tg номер есть в crm у доктора, авторизуем без подтверждения
        else:
            response = await get_sotr_data(phone)
            if response.get("result", {}).get("code") == 0:
                sotr_info = response["result"]["item"]
                if sotr_info["dolj"]:
                    await state.update_data(
                        role="doctor",
                        phone=phone,
                        tg_id=chat_id,
                    )
                    await authenticate_doctor(phone, state)
                    user = await state.get_data()
                    await save_doctor_data(
                        user["name"].split()[1],
                        user["name"].split()[0],
                        user["name"].split()[2],
                        user.get("specialty"),
                        phone,
                        user.get("id_crm"),
                        chat_id,
                    )
                    await processing_msg.delete()
                    await message.answer(auth_success)
                    await handle_auth_doctor(message, state)
                    await state.set_state(DoctorStates.menu)
                    return
            else:
                await processing_msg.delete()
                await message.answer(
                    "Ваш номер телефона не найден в базе. Пожалуйста, отправьте номер телефона вручную,"
                    "который привязан к учетной записи в формате +7XXXXXXXXXX."
                )
                await state.set_state(AuthStates.waiting_for_manual_phone)
    except Exception as e:
        logger.error(f"Ошибка в process_contact: {e}")
        await processing_msg.delete()
        await message.answer(
            "Произошла ошибка. Пожалуйста, повторите попытку. Введите номер вручную."
        )
        await state.set_state(AuthStates.waiting_for_manual_phone)


@auth_router.message(AuthStates.waiting_for_phone, F.content_type != "contact")
async def handle_non_contact_message(message: Message, state: FSMContext):
    """Обрабатывает сообщения, не являющиеся контактами, и сообщает об ошибке."""
    chat_id = message.chat.id
    admin_check_response = await check_if_admin(chat_id)
    if message.text and message.text.strip().lower() == "/admin":
        if admin_check_response:
            await start_admin(message, state)
        else:
            await message.answer(
                "У вас нет прав для входа в режим администратора. Пожалуйста, отправьте свой собственный номер телефона с "
                "помощью кнопки в меню."
            )
        return
    await bot.send_message(
        chat_id=chat_id,
        text="Неверный формат. Пожалуйста, отправьте свой контакт с помощью кнопки в меню.",
    ),


@auth_router.message(AuthStates.waiting_for_manual_phone)
async def process_phone_input(message: Message, state: FSMContext):
    """Обрабатывает ввод номера телефона вручную, проверяет формат и инициирует процесс авторизации."""
    phone = message.text
    chat_id = message.chat.id
    admin_check_response = await check_if_admin(chat_id)

    if phone and phone.strip().lower() == "/admin":
        if admin_check_response:
            await start_admin(message, state)
        else:
            await message.answer(
                "У вас нет прав для входа в режим администратора. "
                "Пожалуйста, введите номер вручную, который привязан к учетной записи в формате +7XXXXXXXXXX."
            )
        return

    if not phone:
        await message.answer(not_correct_manual_phone)
        return

    if not re.match(r"^\+7\d{10}$", phone):
        await message.answer(not_correct_manual_phone)
        return

    processing_msg = await message.answer(waiting_message)
    await state.update_data(tg_id=chat_id)
    await process_phone_number(message, state, phone, processing_msg)


async def process_phone_number(
    message: Message, state: FSMContext, phone=None, processing_msg=None
):
    """
    Обрабатывает номер телефона пользователя, введенный вручную. Определяет его роль (Пациент/Доктор),
    отправляет запрос в поддержку и обновляет состояние.

    :param message: Сообщение от пользователя с номером телефона, введенный вручную.
    :param state: Состояние для сохранения данных.
    :param phone: Номер телефона пользователя.
    :param processing_msg: Сообщение о процессе обработки.
    :return: None
    """
    try:
        if not phone.startswith("+"):
            phone = f"+{phone}"
        tg_id = message.chat.id
        response = await get_user_data(phone)
        if response.get("result", {}).get("code") == 0:
            await asyncio.sleep(3)
            await processing_msg.delete()
            await state.update_data(
                # сохраняю телефон пациента и tg_id в состояние
                role="patient",
                phone=phone,
                tg_id=tg_id,
            )
            await message.answer(wait_for_accept)
            await send_access_request_to_support(message, phone, "Пациент")
            await state.set_state(PatientStates.menu)

        else:
            response = await get_sotr_data(phone)
            if response.get("result", {}).get("code") == 0:
                await asyncio.sleep(3)
                await processing_msg.delete()
                sotr_info = response["result"]["item"]
                if sotr_info["dolj"]:
                    # сохраняю телефон врача и tg_id в состояние
                    await state.update_data(role="doctor", phone=phone, tg_id=tg_id)
                    await message.answer(wait_for_accept)
                    await send_access_request_to_support(message, phone, "Доктор")
                    await state.set_state(DoctorStates.menu)

                else:
                    await message.answer(
                        "Роль не определена. Пожалуйста, введите номер телефона в формате +7XXXXXXXXXX."
                    )
                    await state.set_state(AuthStates.waiting_for_manual_phone)
            else:
                await asyncio.sleep(3)
                await processing_msg.delete()
                await message.answer(
                    "Номер телефона не был найден на сервере. Пожалуйста, введите номер, который привязан к учетной "
                    "записи в формате +7XXXXXXXXXX."
                )
                await state.set_state(AuthStates.waiting_for_manual_phone)

    except Exception as e:
        logger.error(f"Ошибка в process_phone_number: {e}")
        if processing_msg:
            await processing_msg.delete()
        await message.answer(
            "Произошла ошибка. Пожалуйста, введите номер, который привязан к учетной "
            "записи в формате +7XXXXXXXXXX."
        )
        await state.set_state(AuthStates.waiting_for_manual_phone)


@auth_router.callback_query(lambda c: c.data.startswith("approve:"))
async def approve_request(callback_query: CallbackQuery, state: FSMContext):
    """Обрабатывает запрос на подтверждение доступа пользователя (пациента или доктора) и авторизует его в системе."""
    try:
        # данные из callback_data
        data = callback_query.data.split(":")
        chat_id = int(data[1])
        role = data[2]
        phone = data[3]

        user_info = await state.get_data()
        tg_id = chat_id
        await state.update_data(tg_id=tg_id)

        if role == "Пациент":

            await authenticate_patient(phone, state)
            user = await state.get_data()
            client_id = user["id_crm"]
            await save_client_data(
                tg_id,
                user["name"].split()[1],
                user["name"].split()[0],
                user.get("passport"),
                phone,
                user["id_crm"],
                stage=1,
            )
            await set_appointments(client_id, tg_id)
            scenario_null = await get_null_scenarios(0, user["name"].split()[1])
            welcome_message = scenario_null["messages"][0]
            await callback_query.bot.send_message(tg_id, welcome_message.get("content"))
            await handle_patient_command(callback_query.message, state)
            await state.set_state(PatientStates.menu)

        elif role == "Доктор":
            await authenticate_doctor(phone, state)
            user = await state.get_data()
            await save_doctor_data(
                user["name"].split()[1],
                user["name"].split()[0],
                user["name"].split()[2],
                user.get("specialty"),
                phone,
                user.get("id_crm"),
                tg_id,
            )
            await callback_query.bot.send_message(tg_id, auth_success)
            await handle_auth_doctor(callback_query.message, state)
            await state.set_state(DoctorStates.menu)

        await callback_query.message.edit_text("Доступ был одобрен.")
    except Exception as e:
        logger.error(f"Ошибка в approve_request: {e}")
