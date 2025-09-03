import os
import aiohttp

from dotenv import load_dotenv

load_dotenv()

username = os.getenv("USERNAME_CRM")
password = os.getenv("PASSWORD_CRM")
url = os.getenv("URL")


async def get_information(data):
    async with aiohttp.ClientSession() as session:
        async with session.post(
            url, json=data, auth=aiohttp.BasicAuth(username, password)
        ) as response:
            return await response.json()
