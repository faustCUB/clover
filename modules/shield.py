import asyncio
from telethon import events
from telethon.errors import FloodWaitError
from modules.base import BaseModule
from utils import logger

_shield_active = False
_me_id = None
_handler_added = False


async def _incoming_handler(event):
    global _shield_active, _me_id

    if not _shield_active:
        return

    try:
        if event.sender_id and event.sender_id != _me_id:
            await event.delete()
    except FloodWaitError as e:
        await asyncio.sleep(e.seconds)
    except Exception as e:
        logger.error(f"Shield не смог удалить сообщение: {e}")


async def _shield_toggle(event):
    global _shield_active, _me_id, _handler_added
    await event.delete()

    args = event.raw_text.strip().split(maxsplit=1)
    state = args[1].lower() if len(args) > 1 else None

    if state not in ("on", "off"):
        logger.warning("Shield: укажи on или off")
        return

    if _me_id is None:
        me = await event.client.get_me()
        _me_id = me.id

    if not _handler_added:
        event.client.add_event_handler(_incoming_handler, events.NewMessage(incoming=True))
        _handler_added = True

    _shield_active = (state == "on")
    status = "активирован" if _shield_active else "деактивирован"
    logger.success(f"Режим Shield: {logger.accent(status)}")


def setup() -> BaseModule:
    return BaseModule(
        name="Shield",
        version="1.0",
        description="Удаление входящих сообщений",
        commands={
            "shield": _shield_toggle,
        },
        examples=[
            "`.shield on` – включить удаление входящих",
            "`.shield off` – выключить удаление входящих"
        ],
    )