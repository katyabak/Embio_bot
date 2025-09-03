from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

import handlers.functions.admins_fun as hf
import keyboards.admin_kb as kb
import keyboards.constants as kc
from database.admin_db import (
    find_all_doctors,
    find_all_patients,
    logger,
)
from states.states_admin import (
    AdminStates_global,
    AdminStates_find,
)

admin_router = Router()
global all_doctors, prompt_message, all_patients
all_doctors = None
all_patients = None
choice_action = "Выберите нужное действие"


async def start_admin(message: Message, state: FSMContext):
    await message.answer(
        text="Добро пожаловать, админ! Здесь вы можете посмотреть информацию о пациентах, отправить или отредактировать "
             "сценарий.",
        reply_markup=kb.main_admin_kb(),
    )


@admin_router.message(
    AdminStates_global.menu,
    F.text == kc.buttons_admin_menu["find_patient"],
)
async def find_admin(message: Message, state: FSMContext):
    await message.answer(
        "Здесь вы можете найти пациента по трем параметрам: его фамилии, его номеру телефона и по врачу, к которому "
        "он привязан.",
        reply_markup=kb.find_admin_kb(),
    )
    await message.answer("Как именно вы хотите найти пациента?")
    await state.set_state(AdminStates_global.find_patient)


@admin_router.message(
    StateFilter(
        AdminStates_global.find_patient,
        AdminStates_find.surname,
        AdminStates_find.telephone,
        AdminStates_find.doctor_name_first,
        AdminStates_global.change_script,
    ),
    F.text == kc.buttons_admin_back["back"],
)
async def back_to(message: Message, state: FSMContext):
    await message.answer(choice_action, reply_markup=kb.main_admin_kb())
    await state.set_state(AdminStates_global.menu)


@admin_router.message(
    AdminStates_global.find_patient,
    F.text == kc.buttons_admin_find["find_by_surname"],
)
async def find_by_surname(message: Message, state: FSMContext):
    prompt_message = await message.answer(
        "Введите фамилию по образцу: Иванова", reply_markup=kb.back_to_menu_kb()
    )
    await state.update_data(prompt_message_id=prompt_message.message_id)
    await state.set_state(AdminStates_find.surname)


@admin_router.message(
    AdminStates_global.find_patient,
    F.text == kc.buttons_admin_find["find_by_phone"],
)
async def find_by_phone(message: Message, state: FSMContext):
    prompt_message = await message.answer(
        "Введите номер в формате +7XXXXXXXXXX", reply_markup=kb.back_to_menu_kb()
    )
    await state.update_data(prompt_message_id=prompt_message.message_id)
    await state.set_state(AdminStates_find.telephone)


@admin_router.message(
    AdminStates_global.find_patient,
    F.text == kc.buttons_admin_find["find_by_doctor"],
)
async def find_by_doctor(message: Message, state: FSMContext):
    global prompt_message, all_doctors
    if all_doctors is None:
        await message.answer("Собираю информацию...", reply_markup=kb.back_to_menu_kb())
        all_doctors = await find_all_doctors()

    prompt_message = await message.answer(
        "Пациент какого врача вас интересует?",
        reply_markup=kb.inline_doctors_keyboard(all_doctors),
    )
    await state.update_data(prompt_message_id=prompt_message.message_id)
    await state.set_state(AdminStates_find.doctor_name_first)


@admin_router.callback_query(AdminStates_find.doctor_name_first)
async def information_by_doctor(query: CallbackQuery, state: FSMContext):
    await query.answer()
    doctor_id = int(query.data)
    global all_patients, prompt_message

    all_patients = await find_all_patients(doctor_id)
    data = await state.get_data()

    if all_patients:
        await hf.delete_previous_messages(
            query.message.bot, query.message.chat.id, data
        )
        # Удаление сообщения о врачах
        try:
            await query.message.delete()
        except Exception as e:
            logger.exception(f"Error deleting current message: {e}")

        prompt_message = await query.message.answer(
            "Какой именно пациент вас интересует?",
            reply_markup=kb.inline_patients_keyboard(all_patients, "doctors_name"),
        )
        await state.update_data(
            prompt_message_id=prompt_message.message_id, previous_message_ids=[]
        )
        await state.set_state(AdminStates_find.doctor_name_second)
    else:
        no_patients = await query.message.answer(
            "К сожалению, у данного врача нет пациентов. Попробуйте найти пациента по другому врачу или по "
            "фамилии/номеру телефона."
        )
        await state.update_data(
            prompt_message_id=no_patients.message_id,
            previous_message_ids=[no_patients.message_id],
        )


@admin_router.callback_query(AdminStates_find.doctor_name_second)
async def information_by_doctor_second(query: CallbackQuery, state: FSMContext):
    await query.answer()
    global all_patients, prompt_message
    patient_id = query.data

    if patient_id == "back_to_doctors":
        data = await state.get_data()
        await hf.delete_previous_messages(
            query.message.bot, query.message.chat.id, data
        )

        try:
            await query.message.delete()
        except Exception as e:
            logger.exception(f"Ошибка при удалении сообщения: {e}")

        await state.set_state(AdminStates_global.find_patient)
        await find_by_doctor(query.message, state)
        return

    patient_info = next(
        (
            p
            for p in all_patients["result"]["items"]
            if p["patient_id"] == int(patient_id)
        ),
        None,
    )

    if patient_info:
        data = await state.get_data()
        await hf.delete_previous_messages(
            query.message.bot, query.message.chat.id, data, exclude_prompt=True
        )

        response_message = hf.format_patient_info(patient_info)
        new_message = await query.message.answer(response_message)
        prompt_message = await query.message.answer(
            "Интересует ли какой-то пациент ещё? Выберите другого пациента или необходимое действие на клавиатуре."
        )

        await state.update_data(
            previous_message_ids=[new_message.message_id, prompt_message.message_id]
        )


@admin_router.message(AdminStates_find.surname)
async def information_by_last_name(message: Message, state: FSMContext):
    global all_patients
    information = message.text
    all_patients = await hf.find_information(message, state, information, "last_name")


@admin_router.message(AdminStates_find.telephone)
async def information_by_phone(message: Message, state: FSMContext):
    information = message.text
    await hf.find_information(message, state, information, "phone_number")
