from __future__ import annotations
import asyncio
from typing import Awaitable, Callable

# Простой планировщик трёх параллельных циклов

async def periodic(seconds: int, coro_fn: Callable[[], Awaitable[None]]):
    while True:
        try:
            await coro_fn()
        except Exception as e:
            # TODO: логировать исключения
            pass
        await asyncio.sleep(seconds)
