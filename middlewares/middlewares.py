import asyncio

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from typing import Callable, Dict, Any, Awaitable
from aiogram.types import Message

from keyboards.constants import buttons_patient_question


class TestMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        if (
            isinstance(event, Message)
            and event.text == buttons_patient_question["back"]
        ):
            # Если команда Вернуться в меню 🔙, пропускаем выполнение остальной части middlewar
            return await handler(event, data)

        if isinstance(event, Message):
            await event.bot.send_chat_action(chat_id=event.chat.id, action="typing")
            # Задержка в 2 секунды
            await asyncio.sleep(2)

        result = await handler(event, data)
        return result
