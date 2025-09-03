import keyboards.constants as kc

from aiogram.types import KeyboardButton, InlineKeyboardButton
from aiogram.utils.keyboard import (
    ReplyKeyboardBuilder,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
)


def main_admin_kb():
    keyboard = ReplyKeyboardBuilder()

    keyboard.row(
        KeyboardButton(text=kc.buttons_admin_menu["send_script"]),
        KeyboardButton(text=kc.buttons_admin_menu["change_script"]),
    )

    keyboard.row(KeyboardButton(text=kc.buttons_admin_menu["find_patient"]))

    return keyboard.as_markup(
        resize_keyboard=True, input_field_placeholder="Выберите действие"
    )


def changes_admin_kb():
    keyboard = ReplyKeyboardBuilder()

    keyboard.row(
        KeyboardButton(text=kc.buttons_admin_changes["change_patient_script"]),
        KeyboardButton(text=kc.buttons_admin_changes["change_general_script"]),
    )

    keyboard.row(KeyboardButton(text=kc.buttons_admin_back["back"]))

    return keyboard.as_markup(
        resize_keyboard=True, input_field_placeholder="Выберите действие"
    )


def back_to_menu_kb():
    """
    Создает reply-клавиатуру для возвращения назад к основному меню.
    """
    keyboard = ReplyKeyboardBuilder()
    keyboard.add(KeyboardButton(text=kc.buttons_admin_back["back"]))
    return keyboard.as_markup(resize_keyboard=True)


def scenario_selection_keyboard(scenarios):
    """
    Создает reply-клавиатуру для выбора сценария.

    :param scenarios: Словарь с результатами сценариев.
    :return: ReplyKeyboardMarkup объект.
    """
    if scenarios is None or scenarios.get("result") is None:
        return ReplyKeyboardMarkup(keyboard=[], resize_keyboard=True)

    keyboard_buttons = [
        [KeyboardButton(text=scenario["name_stage"])]  # Каждая кнопка в своем ряду
        for scenario in scenarios["result"]["items"]
    ]

    button_back = [KeyboardButton(text=kc.buttons_admin_back["back"])]
    keyboard_buttons.append(button_back)

    keyboard = ReplyKeyboardMarkup(keyboard=keyboard_buttons, resize_keyboard=True)

    return keyboard


def choice_edditing_message():
    keyboard = ReplyKeyboardBuilder()

    keyboard.row(
        KeyboardButton(text=kc.buttons_edditing_scenarios["add"]),
        KeyboardButton(text=kc.buttons_edditing_scenarios["edit"]),
    )
    keyboard.row(KeyboardButton(text=kc.buttons_edditing_scenarios["delete"]))
    keyboard.row(KeyboardButton(text=kc.buttons_admin_back["back"]))

    return keyboard.as_markup(
        resize_keyboard=True, input_field_placeholder="Выберите действие"
    )


def edit_global_choice_keyboard():
    keyboard = ReplyKeyboardBuilder()
    keyboard.add(KeyboardButton(text=kc.buttons_time_or_msg["message"]))
    keyboard.add(KeyboardButton(text=kc.buttons_time_or_msg["time"]))
    keyboard.row(KeyboardButton(text=kc.buttons_admin_back["back"]))
    return keyboard.as_markup(resize_keyboard=True, one_time_keyboard=True)


def back_to_messages_kb():
    """
    Создает клавиатуру для возвращения в меню.

    :return: Клавиатура с кнопкой для возвращения в меню.
    """
    keyboard = ReplyKeyboardBuilder()
    keyboard.add(KeyboardButton(text=kc.buttons_admin_back["back"]))
    return keyboard.as_markup(resize_keyboard=True)


def back_to_scenarios_kb():
    """
    Создает клавиатуру для возвращения в меню сценариев.

    :return: Клавиатура с кнопкой для возвращения в меню сценариев.
    """
    keyboard = ReplyKeyboardBuilder()
    keyboard.add(KeyboardButton(text=kc.buttons_back["back_to"]))
    return keyboard.as_markup(resize_keyboard=True)


def yes_no_keyboard():
    keyboard = ReplyKeyboardBuilder()
    keyboard.add(KeyboardButton(text=kc.buttons_yn["yes"]))
    keyboard.add(KeyboardButton(text=kc.buttons_yn["no"]))

    return keyboard.as_markup(resize_keyboard=True, one_time_keyboard=True)


def general_scenario_choose_keyboard(scenarios):
    """
    Создает reply-клавиатуру для выбора общего сценария.

    :param scenarios: Словарь с результатами сценариев.
    :return: ReplyKeyboardMarkup объект.
    """
    if scenarios is None or scenarios.get("result") is None:
        return ReplyKeyboardMarkup(keyboard=[], resize_keyboard=True)

    # кнопка для каждого сценария
    keyboard_buttons = [
        [KeyboardButton(text=scenario["name_stage"])]
        for scenario in scenarios["result"]["items"]
    ]

    keyboard_buttons.append([KeyboardButton(text="Назад")])

    keyboard = ReplyKeyboardMarkup(keyboard=keyboard_buttons, resize_keyboard=True)

    return keyboard


def find_admin_kb():
    keyboard = ReplyKeyboardBuilder()

    keyboard.row(
        KeyboardButton(text=kc.buttons_admin_find["find_by_surname"]),
        KeyboardButton(text=kc.buttons_admin_find["find_by_doctor"]),
    )

    keyboard.row(KeyboardButton(text=kc.buttons_admin_find["find_by_phone"]))

    keyboard.row(KeyboardButton(text=kc.buttons_admin_find["back_to_menu"]))

    return keyboard.as_markup(
        resize_keyboard=True, input_field_placeholder="Выберите действие"
    )


def inline_doctors_keyboard(directory):
    if directory is None or directory.get("result") is None:
        return InlineKeyboardMarkup(inline_keyboard=[])

    doctors_list = directory["result"]["items"]
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{doctor['doctor_name']}",
                    callback_data=f"{doctor['doctor_id']}",
                )
            ]
            for doctor in doctors_list
        ]
    )
    return keyboard


def inline_patients_keyboard(directory, by_what):
    if directory is None or directory.get("result") is None:
        return InlineKeyboardMarkup(inline_keyboard=[])

    patient_list = directory["result"]["items"]
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{patient['patient_name']}",
                    callback_data=f"{patient['patient_id']}",
                )
            ]
            for patient in patient_list
        ]
    )
    if by_what != "surname":
        keyboard.inline_keyboard.append(
            [
                InlineKeyboardButton(
                    text="Вернуться к выбору врача",
                    callback_data="back_to_doctors",
                )
            ]
        )
    return keyboard
