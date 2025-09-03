import os

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.redis import RedisJobStore
from apscheduler_di import ContextSchedulerDecorator


job_stores = {
    "default": RedisJobStore(
        jobs_key="dispatched_trips_jobs",
        run_times_key="dispatched_trips_running",
        host=os.getenv("REDIS_HOST"),
        port=os.getenv("REDIS_PORT"),
        password=os.getenv("REDIS_PASSWORD"),
    )
}


scheduler = ContextSchedulerDecorator(
    AsyncIOScheduler(timezone="Asia/Omsk", jobstores=job_stores)
)
