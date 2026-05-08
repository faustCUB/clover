import requests
from modules.base import BaseModule
from utils import logger


async def _myip(event):
    try:
        ip = requests.get("https://api.ipify.org", timeout=10).text.strip()
        await event.edit(f"`{ip}`")
        logger.success(f"IP: {logger.accent(ip)}")
    except Exception as e:
        await event.edit(f"❌ Ошибка: `{e}`")
        logger.error(f"Ошибка .myip: {e}")


def setup() -> BaseModule:
    return BaseModule(
        name="MyIP",
        version="1.0",
        description="Показывает твой IP адрес",
        commands={
            "myip": _myip,
        },
        examples=["`.myip`"],
    )
