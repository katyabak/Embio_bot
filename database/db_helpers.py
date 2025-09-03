import logging

from sqlalchemy.future import select
from database.models import Video
from configuration.config_db import SessionLocal

logger = logging.getLogger(__name__)


async def get_url(format_id_url):
    """
    Получение URL видео для заданного сценария.

    :param format_id_url: ID сценария, для которого требуется видео.
    :return: URL видео, если найдено, иначе None.
    """

    try:
        async with SessionLocal() as session:
            async with session.begin():
                stmt = select(Video.video_link).where(
                    Video.for_scenarios == format_id_url
                )
                result = await session.execute(stmt)
                video_link = result.scalar()

                if video_link:
                    return video_link
                else:
                    logger.warning(f"Для сценария {format_id_url} не найдено видео.")
                    return None
    except Exception as e:
        logger.exception(f"Ошибка при получении URL видео для {format_id_url}: {e}")
        return None
