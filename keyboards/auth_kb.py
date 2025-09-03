from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from keyboards.constants import button_auth_find


def get_phone_keyboard():
    """
    Создает клавиатуру с кнопкой для запроса номера телефона.

    :return: Объект ReplyKeyboardMarkup с кнопкой запроса контакта.
    """
    button = KeyboardButton(text=button_auth_find["share_phone"], request_contact=True)
    keyboard = ReplyKeyboardMarkup(keyboard=[[button]], resize_keyboard=True)
    return keyboard


def get_approve_keyboard(chat_id: int, role: str, phone: str):
    """
    Создает инлайн-клавиатуру с кнопкой одобрения.

    :param chat_id: ID чата пользователя.
    :param role: Роль пользователя (пациент или врач).
    :param phone: Номер телефона пользователя.
    :return: Объект InlineKeyboardMarkup с кнопкой "Одобрить".
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Одобрить✅",
                    callback_data=f"approve:{chat_id}:{role}:{phone}",
                )
            ]
        ]
    )
