from datetime import datetime
from typing import Optional

from sqlalchemy import Text, Index
from sqlalchemy.orm import Mapped, mapped_column

from db.database import Base


class Sensor(Base):
    """Информация об устройстве (метаданные)."""

    __tablename__ = "sensors"

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[str] = mapped_column(unique=True, nullable=False)  # Технический ID
    name: Mapped[str] = mapped_column(nullable=False)  # Пользовательское имя
    description: Mapped[Optional[str]] = mapped_column(Text)  # Доп. описание
    online: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=datetime.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.now(), onupdate=datetime.now(), nullable=False
    )


class SensorData(Base):
    """История данных с устройств."""

    __tablename__ = "sensors_data"
    __table_args__ = (
        Index(
            "idx_sensor_device_timestamp",
            "device_id",
            "timestamp",
            postgresql_using="btree",
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[str] = mapped_column(nullable=False)
    timestamp: Mapped[datetime] = mapped_column(default=datetime.now(), nullable=False)
    data: Mapped[str] = mapped_column(Text, nullable=False)  # JSON-строка
    value: Mapped[Optional[float]]
    unit: Mapped[Optional[str]]
