import keyboards.constants as kc
from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder


def doctor_menu_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=kc.buttons_doctor_menu["my_patients"])],
            [KeyboardButton(text=kc.buttons_doctor_menu["find_patient_by_surname"])],
        ],
        resize_keyboard=True,
    )
    return keyboard


def doctor_reply_only_back():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=kc.button_doctor_back["back"])],
        ],
        resize_keyboard=True,
    )
    return keyboard


def doctor_reply_back_and_repeat():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=kc.button_doctor_repeat["repeat"])],
            [KeyboardButton(text=kc.button_doctor_back["back"])],
        ],
        resize_keyboard=True,
    )
    return keyboard


async def inline_treatment_stages_keyboard(stage_number_to_name):
    keyboard = InlineKeyboardBuilder()
    for stage in stage_number_to_name:
        keyboard.add(
            InlineKeyboardButton(
                text=f"{stage_number_to_name[stage]}",
                callback_data=f"{stage}",
            )
        )
    return keyboard.adjust(1).as_markup()


def inline_patients_on_stage_keyboard(stage):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=patient, callback_data=f"patient_{patient}")
                for patient in kc.patients_on_stage.get(stage, {})
            ]
        ]
    )
    return keyboard


async def inline_patients(patients):
    keyboard = InlineKeyboardBuilder()
    for patient in patients:
        if patient["survey_result"] is None:
            smile = kc.no_answers_smile_survey
        elif patient["survey_result"] == "Good":
            smile = kc.positive_smile_survey
        elif patient["survey_result"] == "Normal":
            smile = kc.normal_smile_survey
        else:
            smile = kc.negative_smile_survey
        keyboard.add(
            InlineKeyboardButton(
                text=f'{patient["first_name"]} {patient["last_name"]} {smile}',
                callback_data=f'{patient["phone_number"]}',
            )
        )
    keyboard.add(
        InlineKeyboardButton(
            text=kc.button_doctor_repeat["repeat"], callback_data="repeat"
        )
    )
    return keyboard.adjust(1).as_markup()
