from modules.base import BaseModule
from utils import logger
from telethon.tl.types import Channel, Chat


def format_id(entity) -> str:
    if isinstance(entity, (Channel, Chat)):
        return f"`-100{entity.id}`"
    return f"`{entity.id}`"


async def _id(event):
    args = event.raw_text.strip().split(maxsplit=1)
    arg = args[1] if len(args) > 1 else None

    try:
        if arg and arg.startswith("@"):
            try:
                entity = await event.client.get_entity(arg)
                await event.edit(format_id(entity))
            except Exception as e:
                logger.error(f"ID error: {e}")
            return

        if event.is_reply:
            reply = await event.get_reply_message()
            if reply:
                sender = await reply.get_sender()
                if sender:
                    await event.edit(format_id(sender))
                    return

        entity = await event.get_chat()
        await event.edit(format_id(entity))
        logger.success(f"ID получен: {entity.id}")

    except Exception as e:
        logger.error(f"Ошибка в модуле ID: {e}")


def setup() -> BaseModule:
    return BaseModule(
        name="Id",
        version="1.0",
        description="ID пользователей и чатов",
        commands={
            "id": _id,
        },
        examples=[
            ".id` (реплаем) – получить айди юзера/чата",
            "`.id @username` – получить айди юзера/чата",
        ],
    )