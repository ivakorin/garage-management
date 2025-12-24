import os

from dotenv import dotenv_values

from backend.core.settings import settings


async def test_config():
    assert isinstance(settings.model_dump(), dict)


async def test_config_redis():
    dotenv = dotenv_values(
        dotenv_path=os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "..", ".env"
        )
    )
    path = f"redis://{dotenv.get('GM__REDIS__HOST')}:{dotenv.get('GM__REDIS__PORT')}/0"
    assert path == settings.redis.url
