import asyncio
from telethon import events
from modules.base import BaseModule
from utils import logger

state_storage = {
    "chats": {},
    "global": None
}

_me_id: int | None = None

async def _get_me_id(client) -> int:
    global _me_id
    if _me_id is None:
        me = await client.get_me()
        _me_id = me.id
    return _me_id


async def _auto(event):

    raw = event.raw_text.strip().split(maxsplit=1)
    if len(raw) < 2:
        await event.delete()
        return

    args = raw[1].split()

    if args[0].lower() == "list":
        await _show_list(event)
        return
    if args[0].lower() == "clear":
        await _clear_all(event)
        return

    is_global = args[0].lower() == "all"
    state = args[-1].lower()

    if state not in ("on", "off"):
        await event.delete()
        return

    if is_global:
        text = " ".join(args[1:-1])
        if state == "on":
            if not text:
                await event.delete()
                return
            state_storage["global"] = text
            logger.info(f"Глобальный автоответ включён: {text}")
            await event.delete()
        else:
            state_storage["global"] = None
            logger.info("Глобальный автоответ отключён")
            await event.delete()
    else:
        text = " ".join(args[:-1])
        if state == "on":
            if not text:
                await event.delete()
                return
            state_storage["chats"][event.chat_id] = text
            logger.info(f"Автоответ для чата {event.chat_id} включён: {text}")
            await event.delete()
        else:
            state_storage["chats"].pop(event.chat_id, None)
            logger.info(f"Автоответ для чата {event.chat_id} отключён")
            await event.delete()


async def _show_list(event):
    lines = ["🍀 **Активные автоответы:**"]
    if state_storage["global"]:
        lines.append(f"🌐 Глобальный: `{state_storage['global']}`")
    if state_storage["chats"]:
        lines.append("\nПо чатам:")
        for chat_id, text in state_storage["chats"].items():
            lines.append(f"• `{chat_id}` => `{text}`")
    if not state_storage["global"] and not state_storage["chats"]:
        lines.append("Нет активных автоответов.")
    await event.edit("\n".join(lines))


async def _clear_all(event):
    state_storage["chats"].clear()
    state_storage["global"] = None
    logger.info("Все автоответы очищены")
    await event.delete()


async def _auto_reply_listener(event):
    if event.out:
        return

    chat_id = event.chat_id
    reply_text = state_storage["chats"].get(chat_id) or state_storage["global"]
    if not reply_text:
        return

    try:
        sender = await event.get_sender()
        if sender is None or getattr(sender, 'bot', False):
            return

        me_id = await _get_me_id(event.client)

        is_reply_to_me = False
        if event.is_reply:
            try:
                rep_msg = await event.get_reply_message()
                if rep_msg is not None:
                    is_reply_to_me = rep_msg.sender_id == me_id
            except Exception:
                pass

        if event.is_private or event.mentioned or is_reply_to_me:
            await event.reply(f"**{reply_text}**")
            logger.info(f"Автоответ отправлен в чат {chat_id}")

    except Exception as e:
        logger.error(f"Ошибка в слушателе автоответа: {e}")


def setup() -> BaseModule:
    module = BaseModule(
        name="AvtoOtvet",
        version="1.0",
        description="Автоответчик",
        commands={
            "auto": _auto,
        },
        examples=[
            "`.auto Привет, не сейчас on` – включить автоответ только в текущем чате",
            "`.auto all Я занят on` – включить автоответ во всех чатах",
            "`.auto off` – выключить автоответ в текущем чате",
            "`.auto all off` – выключить автоответ во всех чатах",
            "`.auto list` – посмотреть активные автоответы"
        ],
    )

    module.register_listener = lambda client: client.add_event_handler(
        _auto_reply_listener,
        events.NewMessage(incoming=True)
    )

    return module