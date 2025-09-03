import datetime
import re

from sqlalchemy.future import select

from configuration.config_db import SessionLocal
from database.constants_db import logger
from database.constants_db import procedure_to_stage_number
from database.models import Client, Doctor, Admin, Scenario, UserScenario, Appointment, Video
from handlers.functions.auth_crm_fun import get_book_data, replace_content


async def get_client_info(tg_id):
    """
    Получает информацию о клиенте по его Telegram ID.

    :param tg_id: Telegram ID клиента.
    :return: Объект клиента или None, если клиент не найден.
    """
    async with SessionLocal() as session:
        async with session.begin():
            stmt = select(Client).filter(Client.tg_id == tg_id)
            result = await session.execute(stmt)
            client = result.scalars().first()  # получаем первый результат
            if client:
                return client
            else:
                logger.error(f"Клиент с tg_id {tg_id} не найден")
                return None


async def save_client_data(
        tg_id, first_name, last_name, passport, phone_number, id_crm, stage=None
):
    """
    Сохраняет или обновляет данные клиента в БД.

    :param tg_id: Telegram ID клиента.
    :param first_name: Имя клиента.
    :param last_name: Фамилия клиента.
    :param passport: Паспортные данные клиента.
    :param phone_number: Номер телефона клиента.
    :param id_crm: ID клиента в CRM системе.
    :param stage: Этап клиента (необязательно).
        """
    # Удаление всех нечисловых символов из номера телефона
    phone_number_cleaned = int(
        re.sub(r"\D", "", phone_number)
    )  # заменяет все нецифровые символы на пустоту

    async with SessionLocal() as session:
        async with session.begin():
            stmt = select(Client).filter(Client.tg_id == tg_id)
            result = await session.execute(stmt)
            existing_client = result.scalars().first()
            # преобразуем паспорт в int, если это возможно
            try:
                passport_value = (
                    int(passport) if passport else None
                )  # преобразуем в int
            except ValueError:
                passport_value = None  # если невалидное значение, присваиваем None

            if not existing_client:
                # создание нового клиента, если он не существует
                client = Client(
                    tg_id=tg_id,
                    first_name=first_name,
                    last_name=last_name,
                    passport=passport_value,
                    phone_number=phone_number_cleaned,
                    id_crm=id_crm,
                    stage=stage,
                )
                session.add(client)
            else:
                # обновление существующего клиента, если он уже есть
                existing_client.first_name = first_name
                existing_client.last_name = last_name
                existing_client.passport = passport_value
                existing_client.phone_number = phone_number_cleaned
                existing_client.id_crm = id_crm
                existing_client.stage = stage

            await session.commit()


async def save_doctor_data(
        first_name, last_name, middle_name, specialty, phone_number, id_crm, tg_id
):
    """
    Сохраняет или обновляет данные врача в базе данных.

    :param first_name: Имя врача.
    :param last_name: Фамилия врача.
    :param middle_name: Отчество врача.
    :param specialty: Специальность врача.
    :param phone_number: Номер телефона врача.
    :param id_crm: ID врача в CRM системе.
    :param tg_id: Telegram ID врача.
    """
    # удаление +
    phone_number_cleaned = (
        int(re.sub(r"\D", "", phone_number)) if phone_number else None
    )

    async with SessionLocal() as session:
        async with session.begin():
            stmt = select(Doctor).filter(Doctor.tg_id == tg_id)
            result = await session.execute(stmt)
            existing_doctor = result.scalars().first()

            if not existing_doctor:
                doctor = Doctor(
                    first_name=first_name,
                    last_name=last_name,
                    middle_name=middle_name,
                    specialty=specialty,
                    phone_number=phone_number_cleaned,
                    id_crm=id_crm,
                    tg_id=tg_id,
                )
                session.add(doctor)
            else:
                # обновление данных врача, если он уже существует
                existing_doctor.first_name = first_name
                existing_doctor.last_name = last_name
                existing_doctor.specialty = specialty
                existing_doctor.phone_number = phone_number_cleaned
                existing_doctor.id_crm = id_crm

            await session.commit()


async def check_if_admin(tg_id):
    """
    Проверяет, является ли пользователь администратором.

    :param tg_id: Telegram ID пользователя.
    :return: True, если пользователь является администратором, иначе False.
    """
    async with SessionLocal() as session:
        async with session.begin():
            stmt = select(Admin).filter(Admin.admin_tg_id == tg_id)
            result = await session.execute(stmt)
            admin = result.scalars().first()
            return admin is not None


async def set_appointments(crm_id, chat_id):
    """
    Выставление нового сценария/обновление его в базе данных

    :param crm_id - id пациента из crm
    :param chat_id - тг-id пациента
    """
    async with SessionLocal() as session:
        async with session.begin():
            scheduler_data = await get_book_data(crm_id)
            if (
                    not scheduler_data
                    or "result" not in scheduler_data
                    or "items" not in scheduler_data["result"]
            ):
                return

            appointments = scheduler_data["result"]["items"]
            for appointment in appointments:
                try:
                    t_name = appointment.get("t_name")
                    s_name = appointment.get("s_name")
                    dt_beg = appointment.get("dt_beg")
                    dt_end = appointment.get("dt_end")
                    z_name = appointment.get("z_name")
                    id_tov = appointment.get("id_tov")

                    if id_tov in procedure_to_stage_number:
                        stage = procedure_to_stage_number[id_tov]
                        process = False
                    else:
                        stage = 1
                        process = True

                    if not (t_name and s_name and dt_beg and dt_end):
                        continue

                    doctor_name = s_name.split()
                    if len(doctor_name) < 2:
                        continue

                    doctor_query = select(Doctor).filter(
                        Doctor.first_name == doctor_name[1],
                        Doctor.last_name == doctor_name[0],
                    )
                    doctor_result = await session.execute(doctor_query)
                    doctor = doctor_result.scalars().first()

                    if not doctor:
                        continue

                    client_query = select(Client).where(Client.tg_id == chat_id)
                    client_result = await session.execute(client_query)
                    client = client_result.scalars().first()

                    if not client:
                        raise ValueError(f"Клиент с tg_id={chat_id} не найден")

                    start_time = datetime.datetime.strptime(dt_beg, "%d.%m.%Y %H:%M")
                    end_time = datetime.datetime.strptime(dt_end, "%d.%m.%Y %H:%M")

                    existing_appointment_query = select(Appointment).filter(
                        Appointment.client_id == client.id
                    )
                    existing_appointment_result = await session.execute(
                        existing_appointment_query
                    )
                    existing_appointment = existing_appointment_result.scalars().first()

                    if existing_appointment:
                        if existing_appointment.procedure_id == id_tov:
                            continue
                        elif existing_appointment.procedure_id in procedure_to_stage_number and id_tov in procedure_to_stage_number:
                            if (procedure_to_stage_number[existing_appointment.procedure_id] >
                                    procedure_to_stage_number[id_tov]):
                                continue
                            if existing_appointment.processed == False:
                                continue
                        existing_appointment.client_id = client.id
                        existing_appointment.doctor_id = doctor.id
                        existing_appointment.procedure_id = id_tov
                        existing_appointment.start_time = start_time
                        existing_appointment.end_time = end_time
                        existing_appointment.room_name = z_name
                        existing_appointment.processed = process
                    else:
                        new_appointment = Appointment(
                            client_id=client.id,
                            doctor_id=doctor.id,
                            procedure_id=id_tov,
                            start_time=start_time,
                            end_time=end_time,
                            room_name=z_name,
                            processed=process,
                        )
                        session.add(new_appointment)

                    client.stage = stage
                    await session.commit()
                    await set_scenario(
                        stage, chat_id, client.first_name, doctor.id, start_time
                    )

                except Exception as e:
                    print(f"Ошибка при обработке записи {appointment}: {e}")


async def set_scenario(stage, tg_id, client_first_name, doctor_id, start_time):
    """
    Выставление нового сценария пациенту, в зависимости от того, какое у него расписание в бд

    :param stage - этап пациента
    :param tg_id - тг-id
    :param client_first_name - Имя пациента
    :param doctor_id - id доктора из бд
    :param start_time - дата начала процедуры
    """
    async with SessionLocal() as session:
        async with session.begin():
            try:
                existing_scenario_query = select(UserScenario).where(
                    UserScenario.clients_id == tg_id
                )
                existing_scenario_result = await session.execute(
                    existing_scenario_query
                )
                existing_scenario = existing_scenario_result.scalar_one_or_none()

                # Получаем сценарий по stage
                scenario_query = select(Scenario).where(Scenario.stage == stage)
                scenario_result = await session.execute(scenario_query)
                scenario = scenario_result.scalar_one_or_none()

                if not scenario:
                    raise ValueError(f"Сценарий с stage {stage} не найден")

                # Получаем данные врача
                doctor_query = select(Doctor).where(Doctor.id == doctor_id)
                doctor_result = await session.execute(doctor_query)
                doctor = doctor_result.scalar_one_or_none()

                if not doctor:
                    doctor = None

                # Обновляем сообщения в сценарии
                messages = scenario.scenarios_msg["messages"]

                for message in messages:
                    message_id = message.get("id")

                    updated_message = await replace_content(
                        start_time,
                        message,
                        client_first_name,
                        doctor.first_name if doctor else "",
                        doctor.last_name if doctor else "",
                    )

                    url = await get_videos_doctors(tg_id, doctor.id_crm if doctor else None, stage, message_id)

                    for idx, msg in enumerate(messages):
                        if msg["id"] == message_id:
                            messages[idx] = updated_message
                            if url is not None:
                                messages[idx]["url"] = url
                            break

                if existing_scenario:
                    # Обновляем существующий сценарий
                    existing_scenario.scenarios = scenario.scenarios_msg
                    existing_scenario.stage_msg = stage
                else:
                    # Создаем новый сценарий
                    user_scenario = UserScenario(
                        scenarios=scenario.scenarios_msg, stage_msg=stage, clients_id=tg_id
                    )
                    session.add(user_scenario)

                await session.commit()

                return {"message": "Сценарий успешно сохранен"}
            except Exception as e:
                await session.rollback()
                raise ValueError(f"Ошибка обновления сценария: {str(e)}")


async def get_null_scenarios(stage, first_name):
    """
    Функция, которая отправляет нулевой сценарий пациенту, который только что зарегистрировался

    :param stage - этап пациента (0)
    :param first_name - Имя пациента
    """
    async with SessionLocal() as session:
        async with session.begin():
            try:
                query = select(Scenario).where(Scenario.stage == stage)
                result = await session.execute(query)
                scenario = result.scalar_one_or_none()

                if not scenario:
                    raise ValueError(f"Сценарий с stage {stage} не найден")

                # Убедимся, что scenarios_msg не пустое
                if not scenario.scenarios_msg:
                    raise ValueError(f"Поле scenarios_msg пусто для stage {stage}")

                messages = scenario.scenarios_msg["messages"]

                # Обрабатываем каждое сообщение
                for message in messages:
                    message_id = message.get("id")

                    # Вызываем функцию для замены содержимого
                    updated_message = await replace_content(
                        None, message, first_name, None, None
                    )

                    # Обновляем сообщение в списке
                    for idx, msg in enumerate(messages):
                        if msg["id"] == message_id:
                            messages[idx] = updated_message
                            break
                return scenario.scenarios_msg
            except Exception:
                raise ValueError("Ошибка получения 0 сценария")


async def get_videos_doctors(tg_client, doctor_crm_id, stage, message_id):
    """
    Полуение индивидуальных видео с врачами, для отправки их пациентам

    :param tg_client - тг-id пациента
    :param doctor_crm_id - crm id доктора
    :param stage - этап/id сценария, по которому производится поиск
    :param message_id - номер сообщения, которым отправляется это видео
    """
    async with SessionLocal() as session:
        async with session.begin():
            client_query = select(Client).where(Client.tg_id == tg_client)
            client_result = await session.execute(client_query)
            client = client_result.scalars().first()

            if not client:
                logger.exception(f"Клиент с тг-id не найден: {tg_client}")
                return None

            id_video = f"{stage}.{message_id}.{doctor_crm_id}"

            video_query = select(Video).where(Video.for_scenarios == id_video)
            video_result = await session.execute(video_query)
            video = video_result.scalars().first()

            if not video:
                logger.exception(f"Видео с id не было найдено: {id_video}")
                return None

            url_video = video.video_link
            return url_video
