from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy import AsyncAdaptedQueuePool
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    AsyncAttrs,
    async_sessionmaker,
)
from sqlalchemy.orm import DeclarativeBase

from core.logging import log
from core.settings import settings


class Base(AsyncAttrs, DeclarativeBase):
    __abstract__ = True


DATABASE_URL = settings.database.url

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    poolclass=AsyncAdaptedQueuePool,
)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    factory = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
    log.debug("Session opened")
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            log.error(e)
            await session.rollback()
            raise e
        finally:
            log.debug("Session closed")
            await session.close()


@asynccontextmanager
async def async_session_context():
    async for session in get_async_session():
        try:
            yield session
        except Exception as e:
            log.error(e)
            await session.rollback()
            raise e
        finally:
            await session.close()


async def init_db():
    async with engine.begin() as conn:
        log.info("Initializing database")
        await conn.run_sync(Base.metadata.create_all)
        log.debug("Database initialized")
