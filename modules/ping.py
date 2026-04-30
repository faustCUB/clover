import time
from modules.base import BaseModule
from utils import logger


async def _ping(event):
    start = time.monotonic()
    msg = await event.edit("🏓 Pong!")
    elapsed = (time.monotonic() - start) * 1000
    await msg.edit(f"🏓 Pong! `{elapsed:.0f}ms`")
    logger.info(f"Ping: {logger.accent(f'{elapsed:.0f}ms')}")


def setup() -> BaseModule:
    return BaseModule(
        name="Ping",
        version="1.6.9",
        description="Проверка скорости ответа юзербота",
        commands={
            "ping": _ping,
        },
        examples=["`.ping`"],
    )
