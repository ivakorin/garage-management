import logging

from core.settings import settings


class SQLiteOpFilter(logging.Filter):
    def filter(self, record):
        return "functools.partial" not in record.getMessage()

logging.basicConfig(
    level=settings.log.level,
    format="%(asctime)s [%(levelname)s]   component=%(name)s line=%(lineno)d %(message)s")

logging.getLogger().addFilter(SQLiteOpFilter())

logging.getLogger('aiosqlite').setLevel(logging.WARNING)


log = logging.getLogger(__name__)
