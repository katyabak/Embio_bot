from aiogram.fsm.state import StatesGroup, State


class PatientStates(StatesGroup):
    menu = State()
    ask_question = State()
    ask_survey = State()
    ask_survey_emotion = State()
    info_survey = State()
    survey_preparation = State()
    survey_injection = State()
    no_injection_reason = State()
    wait_for_cancel = State()
    wait_for_response = State()
    awaiting_response = State()
    survey_not_record = State()
    survey_all_good = State()
    survey_all_good_need_help = State()
