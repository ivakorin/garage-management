import os
from urllib.parse import quote

from pydantic_settings import BaseSettings, SettingsConfigDict


class Database(BaseSettings):
    database: str = 'database.db'
    patch: str = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "db", database)

    @property
    def url(self) -> str:
        return f"sqlite+aiosqlite:///{self.patch}"


class Redis(BaseSettings):
    host: str
    port: int
    password: str
    db: int = 0

    @property
    def url(self) -> str:
        escaped_password = quote(self.password, safe='')
        return f"redis://{self.host}:{self.port}/{self.db}"

class Log(BaseSettings):
    level: str

class MQTT(BaseSettings):
    host: str
    port: int
    username: str
    password: str


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        extra="ignore",
        env_prefix="GM__",
        env_file=os.path.abspath(
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".env")
        ),
        case_sensitive=False,
        env_nested_delimiter="__",
    )
    database: Database = Database()
    redis: Redis
    log: Log
    mqtt: MQTT


settings = Settings()
