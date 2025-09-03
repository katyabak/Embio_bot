from aiogram.fsm.state import StatesGroup, State


class DoctorStates(StatesGroup):
    menu = State()
    my_patients = State()
    find_patient_by_surname = State()
    patient_info = State()
    patient_info_back = State()
