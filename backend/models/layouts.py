import json

from sqlalchemy import TEXT
from sqlalchemy.orm import Mapped, mapped_column

from db.database import Base


class Layout(Base):
    __tablename__ = "layouts"
    __table_args__ = {"sqlite_autoincrement": False}  # для SQLite, если нужно
    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    layout: Mapped[str] = mapped_column(TEXT)

    def set_layout(self, data: list):
        """Сохраняет список как JSON-строку"""
        self.layout = json.dumps(data)

    def get_layout(self) -> list:
        """Возвращает список из JSON-строки"""
        return json.loads(self.layout) if self.layout else []
