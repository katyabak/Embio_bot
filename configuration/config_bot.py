import os

from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.redis import RedisStorage
from dotenv import load_dotenv


load_dotenv()
bot = Bot(token=os.getenv("TOKEN"))
storage = RedisStorage.from_url(os.getenv("REDIS_URL"))
dp = Dispatcher(storage=storage)


@dp.message(Command("clear_states"))
async def clear_states(message: Message, state: FSMContext):
    await state.clear()
    await message.bot.send_message(text="Стейт очищен", chat_id=message.chat.id)
