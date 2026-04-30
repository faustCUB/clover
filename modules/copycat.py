from telethon import events
from modules.base import BaseModule
from utils import logger

copycat_storage = {}

async def _cc(event):
    await event.delete()

    args = event.raw_text.split()

    if len(args) > 1 and args[1].lower() == "off":
        if event.chat_id in copycat_storage:
            copycat_storage.pop(event.chat_id)
            logger.success(f"Copycat отключён в чате {event.chat_id}")
        else:
            logger.warning(f"Copycat не был активен в чате {event.chat_id}")
        return

    if len(args) < 2 and not event.is_reply:
        logger.warning("Copycat: не указан пользователь")
        return

    target_user_id = None
    try:
        if event.is_reply:
            reply = await event.get_reply_message()
            if reply is None:
                logger.error("Copycat: не удалось получить сообщение")
                return
            target_user_id = reply.sender_id
        else:
            entity = await event.client.get_entity(args[1])
            target_user_id = entity.id

        if target_user_id:
            copycat_storage[event.chat_id] = target_user_id
            logger.success(f"Copycat активен в чате {event.chat_id} для пользователя {target_user_id}")
        else:
            logger.error("Copycat: не удалось определить пользователя")

    except Exception as e:
        logger.error(f"Copycat ошибка: {e}")


async def _copycat_handler(event):
    if event.out:
        return
    if event.chat_id not in copycat_storage:
        return
    if event.sender_id != copycat_storage[event.chat_id]:
        return

    try:
        if event.media:
            await event.client.send_file(
                event.chat_id,
                event.media,
                caption=event.text or ""
            )
            logger.info(f"Copycat [{event.chat_id}] медиа скопировано | caption: {event.text or '—'}")
        elif event.text:
            await event.client.send_message(event.chat_id, event.text)
            logger.info(f"Copycat [{event.chat_id}] текст скопирован: {event.text}")
    except Exception as e:
        logger.error(f"Copycat error: {e}")


def setup() -> BaseModule:
    module = BaseModule(
        name="Copycat",
        version="1.0",
        description="Повторение сообщений за пользователем",
        commands={
            "cc": _cc,
        },
        examples=[
            "`.cc` @username/реплаем – повторять сообщения пользователя",
            "`.cc off` – не повторять сообщения пользователя"
        ],
    )

    module.register_listener = lambda client: client.add_event_handler(
        _copycat_handler,
        events.NewMessage(incoming=True)
    )

    return module