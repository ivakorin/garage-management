import asyncio

plugins_updated = asyncio.Event()

collector_lock = asyncio.Semaphore(1)
