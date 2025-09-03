import keyboards.constants as kc
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def patient_menu_keyboard():
    """
    Создает клавиатуру для меню пациента с кнопками для расписания и вопросов.

    :return: Клавиатура с кнопками для перехода в меню расписания и отправки вопросов.
    """
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=kc.buttons_patient_menu["schedule"])],
            [KeyboardButton(text=kc.buttons_patient_menu["question"])],
        ],
        resize_keyboard=True,
    )
    return keyboard


def patient_question_keyboard():
    """
    Создает клавиатуру для вопроса пациента с кнопкой для возврата в предыдущее меню.

    :return: Клавиатура с кнопкой для возврата в меню вопросов.
    """
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=kc.buttons_patient_question["back"])]],
        resize_keyboard=True,
    )
    return keyboard


def patient_question_cancel_keyboard():
    """
    Создает клавиатуру для отмены вопроса пациента с кнопками "расписание" и "отменить вопрос".

    :return: Клавиатура с кнопками расписания и отмены вопроса.
    """
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=kc.buttons_patient_cancel["schedule"])],
            [KeyboardButton(text=kc.buttons_patient_cancel["cancel_question"])],
        ],
        resize_keyboard=True,
    )
    return keyboard


def no_question_keyboard():
    """
    Создает клавиатуру с кнопкой для уведомления о том, что вопросов нет.

    :return: Клавиатура с кнопкой для уведомления об отсутствии вопроса.
    """
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=kc.buttons_patient_no_question["no question"])]],
        resize_keyboard=True,
    )
    return keyboard


async def inline_survey(answers):
    keyboard = InlineKeyboardBuilder()
    for answer in answers:
        keyboard.add(
            InlineKeyboardButton(
                text=answers[answer]["text"],
                callback_data=answer,
            )
        )
    return keyboard.adjust(1).as_markup()


async def inline_preparations(preparations):
    keyboard = InlineKeyboardBuilder()
    for preparation in preparations:
        keyboard.add(
            InlineKeyboardButton(
                text=preparations[preparation],
                callback_data=str(preparation),
            )
        )
    return keyboard.adjust(1).as_markup()


def yes_or_no():
    """
    Создает клавиатуру с кнопками "Да" и "Нет" для подтверждения или отмены действия.

    :return: Клавиатура с кнопками для выбора между "Да" и "Нет".
    """
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=kc.buttons_patient_yes_or_no["yes"]),
                KeyboardButton(text=kc.buttons_patient_yes_or_no["no"]),
            ]
        ],
        resize_keyboard=True,
    )
    return keyboard
