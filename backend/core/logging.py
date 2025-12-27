import logging

from backend.core.settings import settings


class SQLiteOpFilter(logging.Filter):
    def filter(self, record):
        return "functools.partial" not in record.getMessage()

logging.basicConfig(
    level=settings.log.level,
    format="%(levelname)s:\t%(asctime)s\t%(message)s"
)

logging.getLogger().addFilter(SQLiteOpFilter())

logging.getLogger('sqlite3').setLevel(logging.WARNING)
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
logging.getLogger('sqlalchemy.dialects.sqlite').setLevel(logging.WARNING)


log = logging.getLogger(__name__)
