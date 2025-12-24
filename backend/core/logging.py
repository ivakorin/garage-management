import logging

from backend.core.settings import settings

logging.basicConfig(
    level=settings.log.level, format="%(levelname)s:\t%(asctime)s\t%(message)s"
)
log = logging.getLogger(__name__)
