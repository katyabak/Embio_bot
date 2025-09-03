from aiogram.fsm.state import StatesGroup, State


class AdminStates_global(StatesGroup):
    menu = State()
    send_script = State()
    change_script = State()
    find_patient = State()


class AdminStates_find(StatesGroup):
    surname = State()
    doctor_name_first = State()
    doctor_name_second = State()
    telephone = State()


class AdminStates_changes(StatesGroup):
    # users scenarios
    find_patient_scenarios = State()
    users_changes_first = State()
    users_choice_edditing = State()
    users_changes_second = State()
    users_changes_waiting = State()
    users_message_or_time = State()
    users_delete_msg = State()
    users_waiting_delete = State()
    users_input_content = State()
    users_input_time = State()
    users_waiting_add = State()
    # general scenarios
    select_scenarios = State()
    general_choice_edditing = State()
    general_delete_msg = State()
    general_waiting_delete = State()
    select_message = State()
    edit_script = State()
    general_waiting_add = State()
    general_message_or_time = State()
    waiting_for_more_editing = State()
    general_input_content = State()
    general_input_time = State()


class SendScenarioStates(StatesGroup):
    waiting_for_phone_number = State()
    waiting_for_message_number = State()
    waiting_for_stage = State()
    waiting_for_more_messages = State()
