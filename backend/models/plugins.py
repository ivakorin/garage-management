import logging
from datetime import datetime

from sqlalchemy.orm import Mapped, mapped_column

from db.database import Base

logger = logging.getLogger(__name__)


class PluginRegistry(Base):
    """Хранит постоянные ID плагинов для консистентности между перезапусками."""

    __tablename__ = "plugin_registry"

    id: Mapped[int] = mapped_column(primary_key=True)
    module_name: Mapped[str] = mapped_column(unique=True, nullable=False)
    class_name: Mapped[str] = mapped_column(nullable=False)
    device_id: Mapped[str] = mapped_column(unique=True, nullable=False)
    is_running: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.now(), onupdate=datetime.now(), nullable=False
    )
