from telethon import events
from modules.base import BaseModule
from utils import logger

_read_chats = set()
_read_all = False


async def _read_incoming(event):
    if event.out:
        return

    if _read_all or event.chat_id in _read_chats:
        try:
            await event.client.send_read_acknowledge(
                entity=event.chat_id,
                max_id=event.id
            )
        except Exception as e:
            logger.error(f"Ошибка авто-чтения: {e}")


async def _toggle_read(event):
    global _read_all
    await event.delete()

    text = event.raw_text.lower()
    args = text.split()

    is_all = "all" in args
    state = None
    if "on" in args:
        state = "on"
    elif "off" in args:
        state = "off"

    if state == "on":
        if is_all:
            _read_all = True
            logger.success("Авто-чтение включено глобально")
        else:
            _read_chats.add(event.chat_id)
            logger.success(f"Авто-чтение включено в чате {event.chat_id}")

    elif state == "off":
        if is_all:
            _read_all = False
            logger.warning("Авто-чтение отключено глобально")
        else:
            _read_chats.discard(event.chat_id)
            logger.warning(f"Авто-чтение отключено в чате {event.chat_id}")

    else:
        await _mark_all_as_read(event)


async def _mark_all_as_read(event):
    try:
        count = 0
        async for dialog in event.client.iter_dialogs():
            if dialog.unread_count > 0:
                try:
                    await event.client.send_read_acknowledge(dialog.entity)
                    count += 1
                except Exception:
                    continue

        logger.success(f"Массово прочитано диалогов: {count}")
    except Exception as e:
        logger.error(f"Ошибка массового прочтения: {e}")


def setup() -> BaseModule:
    module = BaseModule(
        name="Read",
        version="1.0",
        description="Авто-чтение сообщений",
        commands={
            "read": _toggle_read,
        },
        examples=[
            "`.read on` – читать входящие в этом чате",
            "`.read off` – не читать входящие в этом чате",
            "`.read all on` – читать все входящие",
            "`.read all off` – не читать все входящие",
            "`.read` – прочитать все непрочитанные чаты",
        ],
    )

    module.register_listener = lambda client: client.add_event_handler(
        _read_incoming,
        events.NewMessage(incoming=True)
    )

    return module