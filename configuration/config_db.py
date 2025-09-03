import os
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

load_dotenv()

DATABASE_URI = f'postgresql+asyncpg://{os.getenv("POSTGRES_USER")}:{os.getenv("POSTGRES_PASSWORD")}@{os.getenv("POSTGRES_HOST")}:5432/{os.getenv("POSTGRES_DB")}'

engine = create_async_engine(DATABASE_URI, echo=True)
SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass
