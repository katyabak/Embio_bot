import re

from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

import handlers.functions.admins_fun as hf
import keyboards.admin_kb as kb
import keyboards.constants as kc
from database.admin_changes import (
    get_all_scenarios,
    find_patient_scenarios,
    logger,
)
from states.states_admin import (
    AdminStates_global,
    AdminStates_changes,
)

admin_changes_router = Router()
global scenarios
scenarios = None
back_to_choice = "Возвращаю вас к выбору сценария..."
choice_action = "Выберите нужное действие"


@admin_changes_router.message(
    F.text == kc.buttons_admin_back["back"],
    StateFilter(
        AdminStates_changes.find_patient_scenarios,
        AdminStates_changes.users_changes_first,
        AdminStates_changes.users_changes_waiting,
        AdminStates_changes.select_scenarios,
        AdminStates_changes.users_message_or_time,
        AdminStates_changes.general_choice_edditing,
        AdminStates_changes.general_message_or_time,
        AdminStates_changes.waiting_for_more_editing,
        AdminStates_changes.users_input_content,
        AdminStates_changes.users_input_time,
        AdminStates_changes.users_delete_msg,
        AdminStates_changes.general_input_content,
        AdminStates_changes.general_input_time,
        AdminStates_changes.general_delete_msg,
        AdminStates_changes.select_message,
        AdminStates_changes.edit_script
    ),
)
async def back_to_menu(message: Message, state: FSMContext):
    """Возвращение на клавиатуру изменений админа"""
    global scenarios
    scenarios = None
    data = await state.get_data()
    data.clear()
    await state.set_state(AdminStates_global.change_script)
    await message.answer(
        "Что именно вы хотите сделать?", reply_markup=kb.changes_admin_kb()
    )


@admin_changes_router.message(
    AdminStates_global.menu,
    F.text == kc.buttons_admin_menu["change_script"],
)
async def change_admin(message: Message, state: FSMContext):
    """ Кнопка "Изменить сценарии" """
    await message.answer(
        "Здесь вы можете изменить сценарий как конкретного пациента, так и общий. "
        "Что конкретно вы хотите изменить?",
        reply_markup=kb.changes_admin_kb(),
    )
    await state.set_state(AdminStates_global.change_script)


@admin_changes_router.message(
    AdminStates_global.change_script,
    F.text == kc.buttons_admin_changes["change_patient_script"],
)
async def change_patient(message: Message, state: FSMContext):
    """Кнопка изменния сценария у пациента"""
    await message.answer(
        "Введите номер в формате +7XXXXXXXXXX", reply_markup=kb.back_to_menu_kb()
    )
    await state.set_state(AdminStates_changes.find_patient_scenarios)


@admin_changes_router.message(AdminStates_changes.find_patient_scenarios)
async def find_patient_now_scenarios(message: Message, state: FSMContext):
    global scenarios
    information = message.text
    if scenarios is None:
        scenarios = await find_patient_scenarios(information)
    if scenarios and "result" in scenarios and scenarios["result"].get("code") == 0:
        scenario_items = scenarios["result"]["items"]
        name_stage = scenario_items[0]["name_stage"]
        current_part = (
            f"Найден следующий сценарий у данного пациента: '{name_stage}'\n\n"
        )
        await hf.format_scenarios(message.chat.id, current_part, scenario_items)
        await message.answer(
            "Теперь скажите, что вы хотите сделать: отредактировать/удалить сообщения в текущем сценарии или добавить новое?",
            reply_markup=kb.choice_edditing_message(),
        )
        await state.set_state(AdminStates_changes.users_choice_edditing)
    else:
        information = None
        scenarios = None
        await message.answer(
            "Пациент с таким номером телефона не найден. Пожалуйста, попробуйте снова ввести номер телефона."
        )
        await state.set_state(AdminStates_global.change_script)
        await change_patient(message, state)


@admin_changes_router.message(
    AdminStates_changes.users_choice_edditing, F.text == kc.buttons_admin_back["back"]
)
async def hangle_back(message: Message, state: FSMContext):
    global scenarios
    scenarios = None
    await state.set_state(AdminStates_global.change_script)
    await message.answer(
        "Что именно вы хотите сделать?", reply_markup=kb.changes_admin_kb()
    )


@admin_changes_router.message(
    AdminStates_changes.users_choice_edditing,
    F.text == kc.buttons_edditing_scenarios["add"],
)
async def hangle_edit_choice(message: Message, state: FSMContext):
    await message.answer(
        "Теперь начните вводить текст или вставьте ссылку на видео/изображение, которое будет находится в сообщении",
        reply_markup=kb.back_to_menu_kb(),
    )
    await state.set_state(AdminStates_changes.users_input_content)


@admin_changes_router.message(AdminStates_changes.users_input_content)
async def hangle_input_content(message: Message, state: FSMContext):
    if message.content_type != "text":
        get_captions = hf.to_input_media(message)
        url = get_captions.media
        content = get_captions.caption
    else:
        url = ""
        content = message.html_text
    file_type = message.content_type
    if file_type not in ["text", "video", "photo"]:
        await message.answer(
            "К сожалению данный формат не поддерживается. Вы можете отправить снова сообщение с медиа-материалом в виде: фото, видео"
        )
        return

    await message.answer("Теперь введите новое время в формате: (+/-)2 10:00")
    await message.answer(
        "Где:\n +/- - обозначение после поцедуры и до соотвественно.\n2 - количество суток. Если отправка в тот "
        "же день, что и процедура, напишите 0\n10:00 - точное время отправки.\nЕсли какой-то из параметров "
        "отсутствует писать что-либо не обязательно."
    )
    if content is None:
        content = ""
    await state.update_data(content=content, url=url, type=file_type)
    await state.set_state(AdminStates_changes.users_input_time)


@admin_changes_router.message(AdminStates_changes.users_input_time)
async def hangle_input_content(message: Message, state: FSMContext):
    data = await state.get_data()
    content = data.get("content")
    type = data.get("type")
    url = data.get("url")
    time = message.text
    time_pattern = r"^[+-]?\d+(\s\d{1,2}:\d{2})?$"
    if re.match(time_pattern, time):
        await message.answer(
            f"Ваше сообщение будет содержать следующий контент:"
        )
        if type == "photo":
            await message.answer_photo(photo=url, caption=content, parse_mode='HTML')
        elif type == "video":
            await message.answer_video(video=url, caption=content, parse_mode='HTML')
        else:
            await message.answer(content, parse_mode='HTML')
        await message.answer(f"Время отправки: {time}")
        await message.answer(
            "Уверены ли вы в своих изменениях?", reply_markup=kb.yes_no_keyboard()
        )
        await state.update_data(time=time)
        await state.set_state(AdminStates_changes.users_waiting_add)
    else:
        await message.answer(
            "Формат времени некорректный. Попробуйте ввести его ещё раз"
        )
        return


@admin_changes_router.message(
    AdminStates_changes.users_waiting_add, F.text == kc.buttons_yn["yes"]
)
async def handle_delete_msg_yes(message: Message, state: FSMContext):
    global scenarios
    scenario = scenarios["result"]["items"][0]
    data = await state.get_data()
    content = data.get("content")
    url = data.get("url")
    type = data.get("type")
    time = data.get("time")
    result = await hf.add_message_to_scenario(
        scenarios, scenario["scenario_id"], content, time, url, type, "users"
    )
    if result.get("status") == "success":
        await message.answer("Сценарий успешно обновлен.")
    else:
        await message.answer(
            "Возникла ошибка. Возможно проблемы с сохранением в базу данных("
        )
    await message.answer(
        "Хотите продолжить редактирование других сообщений данного пациента?",
        reply_markup=kb.yes_no_keyboard(),
    )
    data.clear()
    await state.set_state(AdminStates_changes.users_changes_waiting)


@admin_changes_router.message(
    AdminStates_changes.users_waiting_add, F.text == kc.buttons_yn["no"]
)
async def handle_delete_msg_no(message: Message, state: FSMContext):
    data = await state.get_data()
    data.clear()
    await state.set_state(AdminStates_changes.find_patient_scenarios)
    await find_patient_now_scenarios(message, state)


@admin_changes_router.message(
    AdminStates_changes.users_choice_edditing,
    F.text == kc.buttons_edditing_scenarios["delete"],
)
async def hangle_edit_choice(message: Message, state: FSMContext):
    await message.answer(
        "Теперь введите номер сообщения из сценария, которое вы хотите удалить"
    )
    await state.set_state(AdminStates_changes.users_delete_msg)


@admin_changes_router.message(AdminStates_changes.users_delete_msg)
async def hangle_delete_msg(message: Message, state: FSMContext):
    number = message.text
    check = await hf.check_number_msg(number, scenarios, message, "delete")
    if check:
        await state.update_data(number=number)
        await state.set_state(AdminStates_changes.users_waiting_delete)
    else:
        return


@admin_changes_router.message(
    AdminStates_changes.users_waiting_delete, F.text == kc.buttons_yn["yes"]
)
async def handle_delete_msg_yes(message: Message, state: FSMContext):
    global scenarios
    data = await state.get_data()
    number = data.get("number")
    result = await hf.delete_and_shift_messages(scenarios, int(number), "users")
    if result.get("status") == "success":
        await message.answer("Сценарий успешно обновлен.")
    else:
        await message.answer(
            "Возникла ошибка. Возможно проблемы с сохранением в базу данных("
        )
    await message.answer(
        "Хотите продолжить редактирование другие сообщений данного пациента?",
        reply_markup=kb.yes_no_keyboard(),
    )
    data.clear()
    await state.set_state(AdminStates_changes.users_changes_waiting)


@admin_changes_router.message(
    AdminStates_changes.users_waiting_delete, F.text == kc.buttons_yn["no"]
)
async def handle_delete_msg_no(message: Message, state: FSMContext):
    data = await state.get_data()
    data.clear()
    await state.set_state(AdminStates_changes.find_patient_scenarios)
    await find_patient_now_scenarios(message, state)


@admin_changes_router.message(
    AdminStates_changes.users_choice_edditing,
    F.text == kc.buttons_edditing_scenarios["edit"],
)
async def handle_edit_choice(message: Message, state: FSMContext):
    await message.answer(
        "Теперь введите номер сообщения из сценария, которое вы хотите отредактировать",
        reply_markup=kb.back_to_menu_kb(),
    )
    await state.set_state(AdminStates_changes.users_changes_first)


@admin_changes_router.message(AdminStates_changes.users_changes_first)
async def editing_message_first(message: Message, state: FSMContext):
    global scenarios

    number = message.text
    check = await hf.check_number_msg(number, scenarios, message, "edit")
    if check:
        await state.update_data(number=number)
        await state.set_state(AdminStates_changes.users_message_or_time)
    else:
        return


@admin_changes_router.message(
    AdminStates_changes.users_message_or_time,
    F.text.in_([kc.buttons_time_or_msg["message"], kc.buttons_time_or_msg["time"]]),
)
async def what_need_changes(message: Message, state: FSMContext):
    choice = message.text
    await hf.edditing_message_or_time(choice, message)
    await state.update_data(choice=choice)
    await state.set_state(AdminStates_changes.users_changes_second)


@admin_changes_router.message(
    AdminStates_changes.users_message_or_time, F.text == kc.buttons_admin_back["back"]
)
async def edditing_back(message: Message, state: FSMContext):
    data = await state.get_data()
    data.clear()
    await state.set_state(AdminStates_changes.find_patient_scenarios)
    await message.answer(
        "Возвращаю вас к выбору сообщения...", reply_markup=kb.back_to_menu_kb()
    )
    await find_patient_now_scenarios(message, state)


@admin_changes_router.message(
    AdminStates_changes.users_changes_second, F.text == kc.buttons_admin_back["back"]
)
async def edditing_back(message: Message, state: FSMContext):
    data = await state.get_data()
    data.clear()
    await state.set_state(AdminStates_changes.users_message_or_time)
    await message.answer("Возвращаю вас к выбору...")
    await message.answer(
        "Скажите, что вы хотите изменить: время отправки или содержимое сообщения?",
        reply_markup=kb.edit_global_choice_keyboard(),
    )


@admin_changes_router.message(
    AdminStates_changes.users_changes_second, F.text != kc.buttons_admin_back["back"]
)
async def editing_message_second(message: Message, state: FSMContext):
    global scenarios
    data = await state.get_data()
    number = data.get("number")
    choice = data.get("choice")
    type = message.content_type
    if type not in ["text", "video", "photo"]:
        await message.answer(
            "К сожалению данный формат не поддерживается. Вы можете отправить снова сообщение с медиа/материалом в виде: фото, видео"
        )
        return
    valid = await hf.edditing_content(choice, message, message.html_text)
    if valid:
        try:
            result = await hf.changin_scenario_in_bd(
                scenarios, number, message, choice, "users"
            )
            if result.get("status") == "success":
                await message.answer("Сценарий успешно обновлен.")
                scenarios = result.get("scenario")
            else:
                await message.answer(
                    "Возникла ошибка. Возможно проблемы с сохранением в базу данных("
                )
            await message.answer(
                "Хотите продолжить редактирование других сообщений данного пациента?",
                reply_markup=kb.yes_no_keyboard(),
            )
            data.clear()
            await state.set_state(AdminStates_changes.users_changes_waiting)
        except Exception as e:
            logger.exception(f"Возникла ошибка: {str(e)}")
    else:
        await message.answer("Попробуйте снова ввести корректные данные.")


@admin_changes_router.message(
    AdminStates_changes.users_changes_waiting, F.text == kc.buttons_yn["yes"]
)
async def yes_edditing_scenarios(message: Message, state: FSMContext):
    await state.set_state(AdminStates_changes.find_patient_scenarios)
    await message.answer(
        "Возвращаю вас к выбору сообщения...", reply_markup=kb.back_to_menu_kb()
    )
    await find_patient_now_scenarios(message, state)


@admin_changes_router.message(
    AdminStates_changes.users_changes_waiting, F.text == kc.buttons_yn["no"]
)
async def no_edditing_scenarios(message: Message, state: FSMContext):
    global scenarios
    scenarios = None
    data = await state.get_data()
    data.clear()
    await state.set_state(AdminStates_global.change_script)
    await message.answer(
        "Что конкретно вы хотите изменить?", reply_markup=kb.changes_admin_kb()
    )


@admin_changes_router.message(
    AdminStates_global.change_script,
    F.text == kc.buttons_admin_changes["change_general_script"],
)
async def change_general(message: Message, state: FSMContext):
    all_scenarios = await get_all_scenarios()
    if not all_scenarios:
        await message.answer("Ошибка при получении сценариев. Попробуйте позже.")
        return
    await message.answer(
        "Выберите общий сценарий для изменения.",
        reply_markup=kb.scenario_selection_keyboard(all_scenarios),
    )
    await state.set_state(AdminStates_changes.select_scenarios)


@admin_changes_router.message(AdminStates_changes.select_scenarios)
async def handle_choose_scenario(message: Message, state: FSMContext):
    global scenarios
    name_stage = message.text
    scenarios = await hf.choose_general_scenario(name_stage, message)
    if scenarios is None:
        await state.set_state(AdminStates_global.change_script)
        await change_general(message, state)
        return
    await message.answer(
        "Теперь скажите, что вы хотите сделать: отредактировать/удалить сообщения в текущем сценарии или добавить новое?",
        reply_markup=kb.choice_edditing_message(),
    )
    await state.set_state(AdminStates_changes.general_choice_edditing)


@admin_changes_router.message(
    AdminStates_changes.general_choice_edditing, F.text == kc.buttons_admin_back["back"]
)
async def hangle_back(message: Message, state: FSMContext):
    global scenarios
    scenarios = None
    await state.set_state(AdminStates_global.change_script)
    await message.answer(
        "Что именно вы хотите сделать?", reply_markup=kb.changes_admin_kb()
    )


@admin_changes_router.message(
    AdminStates_changes.general_choice_edditing,
    F.text == kc.buttons_edditing_scenarios["add"],
)
async def handle_choice_edditing(message: Message, state: FSMContext):
    await message.answer(
        "Теперь начните вводить текст или вставьте ссылку на видео/изображение, которое будет находится в сообщении",
        reply_markup=kb.back_to_menu_kb(),
    )
    await state.set_state(AdminStates_changes.general_input_content)


@admin_changes_router.message(AdminStates_changes.general_input_content)
async def hangle_input_content(message: Message, state: FSMContext):
    if message.content_type != "text":
        get_captions = hf.to_input_media(message)
        url = get_captions.media
        content = get_captions.caption
    else:
        content = message.html_text
        url = ""
    file_type = message.content_type
    if file_type not in ["text", "video", "photo"]:
        await message.answer(
            "К сожалению данный формат не поддерживается. Вы можете отправить снова сообщение с медиа/материалом в виде: фото, видео"
        )
        return

    await message.answer("Теперь введите новое время в формате: (+/-)2 10:00")
    await message.answer(
        "Где:\n +/- - обозначение после поцедуры и до соотвественно.\n2 - количество суток. Если отправка в тот "
        "же день, что и процедура, напишите 0\n10:00 - точное время отправки.\nЕсли какой-то из параметров "
        "отсутствует писать что-либо не обязательно."
    )
    if content is None:
        content = ""

    await state.update_data(content=content, url=url, type=file_type)
    await state.set_state(AdminStates_changes.general_input_time)


@admin_changes_router.message(AdminStates_changes.general_input_time)
async def hangle_input_content(message: Message, state: FSMContext):
    data = await state.get_data()
    content = data.get("content")
    type = data.get("type")
    url = data.get("url")
    time = message.text
    time_pattern = r"^[+-]?\d+(\s\d{1,2}:\d{2})?$"
    if re.match(time_pattern, time):
        await message.answer(
            f"Ваше сообщение будет содержать следующий контент:"
        )
        if type == "photo":
            await message.answer_photo(photo=url, caption=content, parse_mode='HTML')
        elif type == "video":
            await message.answer_video(video=url, caption=content, parse_mode='HTML')
        else:
            await message.answer(content, parse_mode='HTML')
        await message.answer(f"Время отправки: {time}")
        await message.answer(
            "Уверены ли вы в своих изменениях?", reply_markup=kb.yes_no_keyboard()
        )
        await state.update_data(time=time)
        await state.set_state(AdminStates_changes.general_waiting_add)
    else:
        await message.answer(
            "Формат времени некорректный. Попробуйте ввести его ещё раз"
        )
        return


@admin_changes_router.message(
    AdminStates_changes.general_waiting_add, F.text == kc.buttons_yn["yes"]
)
async def handle_delete_msg_yes(message: Message, state: FSMContext):
    global scenarios
    scenario = scenarios["result"]["items"][0]
    data = await state.get_data()
    url = data.get("url")
    type = data.get("type")
    content = data.get("content")
    time = data.get("time")
    result = await hf.add_message_to_scenario(
        scenarios, scenario["scenario_id"], content, time, url, type, "general"
    )
    if result.get("status") == "success":
        await message.answer("Сценарий успешно обновлен.")
    else:
        await message.answer(
            "Возникла ошибка. Возможно проблемы с сохранением в базу данных("
        )
    await message.answer(
        "Хотите продолжить редактирование других сценариев?",
        reply_markup=kb.yes_no_keyboard(),
    )
    data.clear()
    await state.set_state(AdminStates_changes.waiting_for_more_editing)


@admin_changes_router.message(
    AdminStates_changes.general_waiting_add, F.text == kc.buttons_yn["no"]
)
async def handle_delete_msg_no(message: Message, state: FSMContext):
    global scenarios
    scenarios = None
    await state.set_state(AdminStates_global.change_script)
    await change_general(message, state)


@admin_changes_router.message(
    AdminStates_changes.general_choice_edditing,
    F.text == kc.buttons_edditing_scenarios["delete"],
)
async def handle_choice_edditing(message: Message, state: FSMContext):
    await message.answer(
        "Теперь введите номер сообщения из сценария, которое вы хотите удалить",
        reply_markup=kb.back_to_menu_kb(),
    )
    await state.set_state(AdminStates_changes.general_delete_msg)


@admin_changes_router.message(AdminStates_changes.general_delete_msg)
async def handle_general_delete(message: Message, state: FSMContext):
    global scenarios
    number = message.text
    check = await hf.check_number_msg(number, scenarios, message, "delete")
    if check:
        await state.update_data(number=number)
        await state.set_state(AdminStates_changes.general_waiting_delete)
    else:
        return


@admin_changes_router.message(
    AdminStates_changes.general_waiting_delete, F.text == kc.buttons_yn["yes"]
)
async def handle_delete_msg_yes(message: Message, state: FSMContext):
    global scenarios
    data = await state.get_data()
    number = data.get("number")
    result = await hf.delete_and_shift_messages(scenarios, int(number), "general")
    if result.get("status") == "success":
        await message.answer("Сценарий успешно обновлен.")
    else:
        await message.answer(
            "Возникла ошибка. Возможно проблемы с сохранением в базу данных("
        )
    await message.answer(
        "Хотите продолжить редактирование других сценариев?",
        reply_markup=kb.yes_no_keyboard(),
    )
    data.clear()
    await state.set_state(AdminStates_changes.waiting_for_more_editing)


@admin_changes_router.message(
    AdminStates_changes.general_waiting_delete, F.text == kc.buttons_yn["no"]
)
async def handle_delete_msg_no(message: Message, state: FSMContext):
    global scenarios
    scenarios = None
    await state.set_state(AdminStates_global.change_script)
    await change_general(message, state)


@admin_changes_router.message(
    AdminStates_changes.general_choice_edditing,
    F.text == kc.buttons_edditing_scenarios["edit"],
)
async def handle_choice_edditing(message: Message, state: FSMContext):
    await message.answer(
        "Теперь введите номер сообщения, которое вы хотите отредактировать",
        reply_markup=kb.back_to_menu_kb(),
    )
    await state.set_state(AdminStates_changes.select_message)


@admin_changes_router.message(
    AdminStates_changes.select_message, F.text != kc.buttons_admin_back["back"]
)
async def handle_select_scenario_message(message: Message, state: FSMContext):
    global scenarios

    number = message.text
    if number == "Назад":
        scenarios = await get_all_scenarios()
        keyboard = kb.scenario_selection_keyboard(scenarios)
        await message.answer(back_to_choice)
        await message.answer(
            "Выберите общий сценарий для изменения.", reply_markup=keyboard
        )
        await state.set_state(AdminStates_global.change_script)
        return

    check = await hf.check_number_msg(number, scenarios, message, "edit")
    if check:
        await state.update_data(number=number)
        await state.set_state(AdminStates_changes.general_message_or_time)
    else:
        return


@admin_changes_router.message(
    AdminStates_changes.general_message_or_time,
    F.text.in_([kc.buttons_time_or_msg["message"], kc.buttons_time_or_msg["time"]]),
)
async def edit_choice(message: Message, state: FSMContext):
    choice = message.text
    await hf.edditing_message_or_time(choice, message)
    await state.set_state(AdminStates_changes.edit_script)
    await state.update_data(choice=choice)


@admin_changes_router.message(
    AdminStates_changes.general_message_or_time, F.text == kc.buttons_admin_back["back"]
)
async def edit_choice_back(message: Message, state: FSMContext):
    global scenarios
    scenarios = None
    await message.answer(choice_action, reply_markup=kb.changes_admin_kb())
    await state.set_state(AdminStates_global.change_script)


@admin_changes_router.message(
    AdminStates_changes.edit_script, F.text != kc.buttons_admin_back["back"]
)
async def handle_edit_time(message: Message, state: FSMContext):
    global scenarios

    data = await state.get_data()
    number = data.get("number")
    choice = data.get("choice")
    if message.text == "Назад":
        scenarios = await get_all_scenarios()
        keyboard = kb.scenario_selection_keyboard(scenarios)
        await message.answer(back_to_choice, reply_markup=kb.back_to_menu_kb())
        await message.answer(
            "Выберите общий сценарий для изменения.", reply_markup=keyboard
        )
        await state.set_state(AdminStates_global.change_script)
        return
    if message.content_type not in ["text", "video", "photo"]:
        await message.answer(
            "К сожалению данный формат не поддерживается. Вы можете отправить снова сообщение с медиа/материалом в виде: фото, видео"
        )
        return
    valid = await hf.edditing_content(choice, message, message.html_text)
    if valid:
        try:
            result = await hf.changin_scenario_in_bd(
                scenarios, number, message, choice, "general"
            )
            if result.get("status") == "success":
                await message.answer("Сценарий успешно обновлен.")
                scenarios = result.get("scenario")
            else:
                await message.answer(
                    "Возникла ошибка. Возможно проблемы с сохранением в базу данных("
                )
            await message.answer(
                "Хотите продолжить редактирование других сценариев?",
                reply_markup=kb.yes_no_keyboard(),
            )
            data.clear()
            await state.set_state(AdminStates_changes.waiting_for_more_editing)
        except Exception as e:
            logger.exception(f"Возникла ошибка: {str(e)}")
    else:
        await message.answer("Попробуйте снова ввести корректные данные.")


@admin_changes_router.message(
    F.text == kc.buttons_yn["yes"], AdminStates_changes.waiting_for_more_editing
)
async def handle_edit_more(message: Message, state: FSMContext):
    await message.answer(back_to_choice, reply_markup=kb.back_to_menu_kb())
    await state.set_state(AdminStates_global.change_script)
    await change_general(message, state)


@admin_changes_router.message(
    F.text == kc.buttons_yn["no"], AdminStates_changes.waiting_for_more_editing
)
async def handle_stop_editing(message: Message, state: FSMContext):
    global scenarios
    scenarios = None
    await message.answer(choice_action, reply_markup=kb.changes_admin_kb())
    await state.set_state(AdminStates_global.change_script)
