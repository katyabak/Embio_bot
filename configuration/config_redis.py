import os
import redis
from dotenv import load_dotenv

load_dotenv()

redis_host = os.getenv("REDIS_HOST")
redis_port = os.getenv("REDIS_PORT")
redis_password = os.getenv("REDIS_PASSWORD")


# Подключение к Redis
def get_redis_client():
    return redis.StrictRedis(
        host=redis_host, port=int(redis_port), password=redis_password, db=0
    )
