import logging

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

import keyboards.admin_kb as kb
import keyboards.constants as kc
import handlers.functions.admin_send_fun as hf
from database.admin_send_db import get_general_scenarios, get_general_scenario_data
from states.states_admin import (
    AdminStates_global,
    SendScenarioStates,
)

admin_send_script = Router()
choice_action = "Выберите нужное действие"
write_phone = "Введите номер телефона пациента в формате +7XXXXXXXXXX:"
logger = logging.getLogger(__name__)


@admin_send_script.message(
    F.text == "Назад", SendScenarioStates.waiting_for_stage
)
async def back_to_send_phone(message: Message, state: FSMContext):
    """Возвращает пользователя к вводу номера телефона пациента."""
    await message.answer(write_phone, reply_markup=kb.back_to_messages_kb())
    await state.set_state(AdminStates_global.send_script)


@admin_send_script.message(
    AdminStates_global.menu, F.text == kc.buttons_admin_menu["send_script"]
)
async def send_admin(message: Message, state: FSMContext):
    """Начинает процесс отправки сценария, запрашивает номер телефона пациента."""
    await message.answer(
        write_phone,
        reply_markup=kb.back_to_messages_kb(),
    )
    await state.set_state(AdminStates_global.send_script)


@admin_send_script.message(SendScenarioStates.waiting_for_stage)
async def handle_stage_selection_message(message: Message, state: FSMContext):
    """Обрабатывает выбор этапа сценария и загружает соответствующие данные сценария."""
    try:
        scenarios = await get_general_scenarios()
        if not scenarios or "result" not in scenarios:
            await message.answer(
                "Ошибка при получении списка сценариев. Попробуйте позже."
            )
            return

        # находим сценарий по имени этапа (текст кнопки)
        scenario_data = next(
            (
                scenario
                for scenario in scenarios["result"]["items"]
                if scenario["name_stage"].strip().lower()
                == message.text.strip().lower()
            ),
            None,
        )

        if not scenario_data:
            await message.answer("Сценарий не найден.")
            return

        # получаем данные сценария по name_stage
        scenario_details = await get_general_scenario_data(scenario_data["name_stage"])
        if not scenario_details or "messages" not in scenario_details:
            await message.answer(
                "Ошибка при получении данных сценария. Попробуйте позже."
            )
            return

        await state.update_data(
            scenario_id=scenario_data["scenario_id"],
            messages=scenario_details["messages"],
        )

        await hf.send_message_list(message, state)

        await state.set_state(SendScenarioStates.waiting_for_message_number)

    except Exception as e:
        logger.exception(f"Ошибка при выборе сценария: {e}")
        await message.answer(
            "Произошла ошибка при получении данных сценария. Попробуйте снова.",
            reply_markup=kb.back_to_messages_kb(),
        )


@admin_send_script.message(AdminStates_global.send_script)
async def process_phone_number_wrapper(message: Message, state: FSMContext):
    """Обрабатывает ввод номера телефона пациента."""
    await hf.process_phone_number(message, state)


@admin_send_script.message(SendScenarioStates.waiting_for_message_number)
async def process_message_number_wrapper(message: Message, state: FSMContext):
    """Обрабатывает номер сообщения для отправки сценария."""
    data = await state.get_data()
    id = data.get("scenario_id")
    await hf.process_message_number(message, state, id)


@admin_send_script.message(F.text == "Да", SendScenarioStates.waiting_for_more_messages)
async def handle_send_more(message: Message, state: FSMContext):
    """Запрашивает следующий номер телефона пациента для отправки сценария."""
    await message.answer(
        "Введите номер телефона пациента в формате +7XXXXXXXXXX:",
        reply_markup=kb.back_to_messages_kb(),
    )
    await state.set_state(AdminStates_global.send_script)


@admin_send_script.message(
    F.text == "Нет", SendScenarioStates.waiting_for_more_messages
)
async def handle_stop_sending(message: Message, state: FSMContext):
    """Останавливает процесс отправки сообщений и возвращает в меню выбора действия."""
    await message.answer(choice_action, reply_markup=kb.main_admin_kb())
    await state.set_state(AdminStates_global.menu)
