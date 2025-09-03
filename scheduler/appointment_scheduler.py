import logging
from datetime import datetime, timedelta

from database.auth_db import set_appointments
from scheduler.scenario_helpers import (
    get_telegram_id,
    get_users_scenarios,
    mark_appointment_as_processed,
    get_new_appointments,
    list_clients,
)
from scheduler.sched_tasks import (
    schedule_scenario_message,
    check_after_4331_procedure,
)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


async def calculate_send_time(start_time, offset_time):
    """
    Рассчет времени для отправки сообщений

    :param start_time - время начала процедуры из бд
    :param offset_time - время, в которое необходимо отправить сообщение (из сценария)
    """
    try:
        if isinstance(start_time, datetime):
            start_datetime = start_time
        elif isinstance(start_time, str):
            start_datetime = datetime.fromisoformat(start_time)
        else:
            logging.error(f"Invalid type for start_time: {type(start_time)}")
            return None

        if " " in offset_time:
            days_offset, time_of_day = offset_time.split()
            time_offset = int(days_offset)
            send_time = start_datetime + timedelta(hours=time_offset)
            return datetime.combine(
                send_time.date(), datetime.strptime(time_of_day, "%H:%M").time()
            )
        elif offset_time == "0":
            return datetime.now() + timedelta(seconds=5)
        else:
            time_offset = int(offset_time)
            return start_datetime + timedelta(hours=time_offset)
    except ValueError as e:
        logging.error(f"Invalid time format in calculate_send_time: {e}")
        return None


async def handle_new_appointment(ctx, appointment):
    """
    Подготовка контента для отправки

    :param appointment - запись из таблицы appointment
    """
    procedure_id = appointment["procedure_id"]
    get_id = await get_telegram_id(appointment["client_id"])
    telegram_id = get_id["tg_id"]
    if not telegram_id:
        return

    scenarios = await get_users_scenarios(telegram_id)
    if scenarios and "messages" in scenarios and scenarios["messages"]:
        for message in scenarios["messages"]:
            send_time = await calculate_send_time(
                appointment["start_time"], message["time"]
            )
            if send_time:
                message_type = message.get("type")
                id_survey = message.get("id_survey")
                if procedure_id == 4331:
                    await check_after_4331_procedure(ctx, telegram_id, appointment["client_id"],
                                                     appointment["start_time"])
                else:
                    await schedule_scenario_message(
                        ctx,
                        telegram_id,
                        message["id"],
                        send_time,
                        message["content"],
                        message["url"],
                        message_type,
                        id_survey=id_survey if id_survey else -1,
                    )

            else:
                logging.warning(
                    f"Skipping message {message['id']} due to invalid time format"
                )
        await mark_appointment_as_processed(appointment["id"])
    else:
        await mark_appointment_as_processed(appointment["id"])
        logging.info(f"No messages found for procedure {procedure_id}")


async def check_new_appointments(ctx):
    """
    Промежуточкая функция для проверки на наличие сценария на отправку
    """
    logging.info("Checking for new appointments...")
    new_appointments = await get_new_appointments()
    for appointment in new_appointments:
        await handle_new_appointment(ctx, appointment)


async def update_appointments(ctx):
    """
    Проверка и обновление расписания в бд
    """
    try:
        clients = await list_clients()

        for client in clients:
            crm_id = client["crm_id"]
            tg_id = client["tg_id"]

            logging.info(f"Обновление расписания для CRM ID: {crm_id}, TG ID: {tg_id}")
            await set_appointments(crm_id, tg_id)

        logging.info("Обновление расписаний завершено.")

    except Exception as e:
        logging.exception(f"Ошибка при обновлении расписаний: {e}")
