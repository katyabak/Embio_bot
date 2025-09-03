from aiogram import types, Router, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

import keyboards.doctor_kb as kb
import keyboards.constants as kc
from states.states_doctor import DoctorStates
from database.find_for_doctor import (
    get_patients_by_doctor_phone,
    get_patient_surveys_answers_by_phone,
)
from configuration.config_bot import bot
from database.constants_db import stage_number_to_name


doctor_router = Router()
doctor_phone = "77777777777"


async def handle_auth_doctor(message: types.Message, state: FSMContext):
    global doctor_phone
    user_data = await state.get_data()
    if doctor_phone is None:
        doctor_phone = user_data.get("phone")

    tg_id = user_data.get("tg_id")
    if tg_id:
        await message.bot.send_message(
            tg_id,
            text="Выберите действие в меню:",
            reply_markup=kb.doctor_menu_keyboard(),
        )
        await state.set_state(DoctorStates.menu)


@doctor_router.message(Command("doctor"))
async def handler_doctor_command(message: types.Message, state: FSMContext):
    await message.answer(
        text="Выберите действие в меню:", reply_markup=kb.doctor_menu_keyboard()
    )
    await state.set_state(DoctorStates.menu)


@doctor_router.message(
    StateFilter(DoctorStates.my_patients, DoctorStates.patient_info),
    F.text == kc.button_doctor_back["back"],
)
async def return_from_my_patients(message: types.Message, state: FSMContext):
    data = await state.get_data()
    message_id = data.get("message_id")
    await message.bot.delete_message(message_id=message_id, chat_id=message.chat.id)
    await message.bot.delete_message(message_id=message_id - 1, chat_id=message.chat.id)
    await message.answer(
        "Выберите действие в меню", reply_markup=kb.doctor_menu_keyboard()
    )
    await state.set_state(DoctorStates.menu)


@doctor_router.message(
    F.text == kc.button_doctor_back["back"],
    StateFilter(DoctorStates.find_patient_by_surname, DoctorStates.patient_info_back),
)
async def back_to_menu(message: types.Message, state: FSMContext):
    await message.answer(
        "Выберите действие в меню", reply_markup=kb.doctor_menu_keyboard()
    )
    await state.set_state(DoctorStates.menu)


@doctor_router.message(
    StateFilter(DoctorStates.patient_info, DoctorStates.patient_info_back),
    F.text == kc.button_doctor_repeat["repeat"],
)
async def my_patients_handler(message: types.Message, state: FSMContext):
    await message.answer(
        "Выберите пациента на нужном этапе лечения",
        reply_markup=kb.doctor_reply_only_back(),
    )
    message_answer = await message.answer(
        "Этапы лечения:",
        reply_markup=await kb.inline_treatment_stages_keyboard(stage_number_to_name),
    )
    await state.update_data(message_id=message_answer.message_id)
    await state.set_state(DoctorStates.my_patients)


@doctor_router.message(
    DoctorStates.menu, F.text == kc.buttons_doctor_menu["my_patients"]
)
async def my_patients_handler(message: types.Message, state: FSMContext):
    await message.answer(
        "Выберите пациента на нужном этапе лечения",
        reply_markup=kb.doctor_reply_only_back(),
    )
    message_answer = await message.answer(
        "Этапы лечения:",
        reply_markup=await kb.inline_treatment_stages_keyboard(stage_number_to_name),
    )
    await state.update_data(message_id=message_answer.message_id)
    await state.set_state(DoctorStates.my_patients)


@doctor_router.message(
    DoctorStates.menu, F.text == kc.buttons_doctor_menu["find_patient_by_surname"]
)
async def find_patient_by_surname_handler(message: types.Message, state: FSMContext):
    await message.answer(
        "Введите фамилию по образцу: Иванова", reply_markup=kb.doctor_reply_only_back()
    )
    await state.set_state(DoctorStates.find_patient_by_surname)


@doctor_router.message(DoctorStates.find_patient_by_surname)
async def find_patient_command(message: types.Message):
    surname = message.text
    find_result_all = await get_patients_by_doctor_phone(doctor_phone)
    find_result = find_result_all["result"]
    find_list = []
    for el in find_result["patients"]:
        if surname in el.values():
            first_name = el["first_name"]
            last_name = el["last_name"]
            tg_id = el["tg_id"]
            phone_number = el["phone_number"]
            stage = el["stage"]
            survey_result = el["survey_result"]

            find_list.append(
                {
                    "first_name": first_name,
                    "last_name": last_name,
                    "tg_id": tg_id,
                    "phone_number": phone_number,
                    "stage": stage,
                    "survey_result": survey_result,
                }
            )
    if len(find_list) >= 1:
        await message.answer("Найден(ы) пациент(ы) ✨")
        for patient in find_list:
            full_info = await bot.get_chat(patient["tg_id"])
            await message.answer(
                f'<b>Пациент</b>: {patient["last_name"]} {patient["first_name"]}\n'
                f'<b>Телефон</b>: +{patient["phone_number"]}\n'
                f"<b>Аккаунт</b>: @{full_info.username}\n"
                f'<b>Текущий сценарий</b>: {stage_number_to_name[patient["stage"]]}\n',
                parse_mode="HTML",
                reply_markup=kb.doctor_reply_only_back(),
            )
            patient_surveys_all = await get_patient_surveys_answers_by_phone(
                patient["phone_number"]
            )

            patient_surveys = patient_surveys_all["surveys_answers"]

            if patient_surveys is None:
                await message.answer("У пациента нет пройденных опросов ☺️")
            else:
                await message.answer("Опросы, пройденные пациентом ⬇️")
                for survey in patient_surveys:
                    out_text = ""
                    out_text += f"<b>Опрос:</b> {survey['title']}\n\n"
                    if "answers" in survey:
                        for answer in survey["answers"]:
                            out_text += f"<b>Вопрос:</b> {answer['question']}\n"
                            out_text += f"<b>Ответ:</b> {answer['answer']}\n\n"
                    else:
                        out_text += f"Опрос пройден без нареканий 🥰"
                    await message.answer(out_text, parse_mode="HTML")
    else:
        await message.answer(
            "Пациентов не найдено 😞", reply_markup=kb.doctor_reply_only_back()
        )
    await message.answer("Вы можете ввести фамилию повторно или вернуться в меню")


@doctor_router.callback_query(DoctorStates.my_patients)
async def treatment_stage_callback(query: CallbackQuery, state: FSMContext):
    stage = int(query.data)
    find_result = await get_patients_by_doctor_phone(doctor_phone)
    find_result_all = find_result["result"]
    find_list_all = []
    for el in find_result_all["patients"]:
        if stage == el["stage"]:
            first_name = el["first_name"]
            last_name = el["last_name"]
            tg_id = el["tg_id"]
            phone_number = el["phone_number"]
            survey_result = el["survey_result"]

            find_list_all.append(
                {
                    "first_name": first_name,
                    "last_name": last_name,
                    "tg_id": tg_id,
                    "phone_number": phone_number,
                    "stage": stage,
                    "survey_result": survey_result,
                }
            )
    if len(find_list_all) >= 1:
        message_answer = await query.message.edit_text(
            "Выберите нужного пациента:",
            reply_markup=await kb.inline_patients(find_list_all),
        )
        await state.update_data(
            find_list_all=find_list_all, message_id=message_answer.message_id
        )
        await state.set_state(DoctorStates.patient_info)
    else:
        await state.set_state(DoctorStates.patient_info_back)
        await query.message.delete()
        await query.message.answer("Пациентов не найдено 😞")
        message_answer = await query.message.answer(
            "Что ещё хотите сделать?", reply_markup=kb.doctor_reply_back_and_repeat()
        )
        await state.update_data(message_id=message_answer.message_id)


@doctor_router.callback_query(DoctorStates.patient_info)
async def patient_info_callback(query: CallbackQuery, state: FSMContext):
    if query.data != "repeat":

        await query.message.delete()
        data = await state.get_data()
        find_list_all = data.get("find_list_all")
        phone = int(query.data)
        for patient in find_list_all:
            if patient["phone_number"] == phone:
                full_info = await bot.get_chat(patient["tg_id"])
                await query.message.answer(
                    f'<b>Пациент</b>: {patient["last_name"]} {patient["first_name"]}\n'
                    f'<b>Телефон</b>: +{patient["phone_number"]}\n'
                    f"<b>Аккаунт</b>: @{full_info.username}\n"
                    f'<b>Текущий сценарий</b>: {stage_number_to_name[patient["stage"]]}\n',
                    parse_mode="HTML",
                )
                break

        patient_surveys_aw = await get_patient_surveys_answers_by_phone(str(phone))
        patient_surveys = patient_surveys_aw["surveys_answers"]

        if patient_surveys is None:
            await query.message.answer("У пациента нет пройденных опросов ☺️")
        else:
            await query.message.answer("Опросы, пройденные пациентом ⬇️")
            for survey in patient_surveys:
                out_text = ""
                out_text += f"<b>Опрос:</b> {survey['title']}\n\n"
                if "answers" in survey:
                    for answer in survey["answers"]:
                        out_text += f"<b>Вопрос:</b> {answer['question']}\n"
                        out_text += f"<b>Ответ:</b> {answer['answer']}\n\n"
                else:
                    out_text += f"Опрос пройден без нареканий 🥰"
                await query.message.answer(out_text, parse_mode="HTML")

        await query.message.answer(
            "Что ещё хотите сделать?", reply_markup=kb.doctor_reply_back_and_repeat()
        )
        await state.set_state(DoctorStates.patient_info_back)

    else:

        message_answer = await query.message.edit_text(
            "Этапы лечения:",
            reply_markup=await kb.inline_treatment_stages_keyboard(
                stage_number_to_name
            ),
        )
        await state.update_data(message_id=message_answer.message_id)
        await state.set_state(DoctorStates.my_patients)
