from datetime import datetime
from typing import Optional

from sqlalchemy import Text
from sqlalchemy.orm import Mapped, mapped_column

from db.database import Base


class Device(Base):
    """Информация об устройстве (метаданные)."""
    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[str] = mapped_column(unique=True, nullable=False)  # Технический ID
    name: Mapped[str] = mapped_column(nullable=False)  # Пользовательское имя
    description: Mapped[Optional[str]] = mapped_column(Text)  # Доп. описание
    created_at: Mapped[datetime] = mapped_column(default=datetime.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.now(),
        onupdate=datetime.now(),
        nullable=False
    )


class DeviceData(Base):
    """История данных с устройств."""
    __tablename__ = "device_data"

    id:Mapped[int] = mapped_column(primary_key=True)
    device_id:Mapped[str] = mapped_column(nullable=False)
    timestamp:Mapped[datetime] =mapped_column(default=datetime.now(), nullable=False)
    data:Mapped[str] = mapped_column(Text, nullable=False)  # JSON-строка
    value:Mapped[Optional[float]]  # Опционально: числовое значение для агрегации