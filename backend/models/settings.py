from sqlalchemy import Text
from sqlalchemy.orm import Mapped, mapped_column

from db.database import Base


class SystemSetting(Base):
    """Глобальные настройки системы."""
    __tablename__ = "system_settings"

    key:Mapped[str]= mapped_column(primary_key=True)
    value:Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str]

    @classmethod
    def get_int(cls, session, key, default=None):
        row = session.query(cls).filter(cls.key == key).first()
        if row:
            return int(row.value)
        return default
