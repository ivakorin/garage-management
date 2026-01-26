from datetime import datetime
from typing import Optional

from sqlalchemy import Text, Index
from sqlalchemy.orm import Mapped, mapped_column

from db.database import Base


class Actuator(Base):
    __tablename__ = "actuators"
    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[str] = mapped_column(unique=True, nullable=False)
    name: Mapped[str] = mapped_column(nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    pin: Mapped[int] = mapped_column(unique=True, nullable=False)
    inverted: Mapped[bool] = mapped_column(default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    last_command: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=datetime.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.now(), onupdate=datetime.now(), nullable=False
    )


class ActuatorCommand(Base):
    __tablename__ = "actuator_commands"

    __table_args__ = (Index("idx_actuator_device_timestamp", "device_id", "timestamp"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[str] = mapped_column(
        nullable=False,
        unique=False,
    )
    timestamp: Mapped[datetime] = mapped_column(default=datetime.now(), nullable=False)
    command: Mapped[str] = mapped_column(nullable=False, unique=False)
    success: Mapped[bool] = mapped_column(nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    payload: Mapped[Optional[str]] = mapped_column(Text)
