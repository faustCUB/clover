import asyncio
from telethon.tl.functions.messages import SetTypingRequest
from telethon.tl.types import SendMessageTypingAction
from modules.base import BaseModule
from utils import logger

typing_chats = {}


async def _tp(event):
    await event.delete()

    args = event.raw_text.strip().split(maxsplit=1)
    chat_id = event.chat_id
    action = args[1].lower() if len(args) > 1 else ""

    if action == "off":
        if chat_id in typing_chats:
            typing_chats[chat_id] = False
            logger.success(f"Тайпинг остановлен в чате {chat_id}")
        else:
            logger.warning(f"Тайпинг не был запущен в чате {chat_id}")
        return

    if typing_chats.get(chat_id):
        logger.warning(f"Тайпинг уже запущен в чате {chat_id}")
        return

    typing_chats[chat_id] = True
    asyncio.create_task(_typing_loop(event.client, chat_id))
    logger.success(f"Тайпинг запущен в чате {chat_id}")


async def _typing_loop(client, chat_id):
    try:
        while typing_chats.get(chat_id):
            try:
                await client(SetTypingRequest(
                    peer=chat_id,
                    action=SendMessageTypingAction()
                ))
                await asyncio.sleep(4)
            except Exception as e:
                logger.error(f"Ошибка отправки тайпинга: {e}")
                break
    finally:
        typing_chats.pop(chat_id, None)
        logger.info(f"Цикл тайпинга завершён для {chat_id}")


def setup() -> BaseModule:
    return BaseModule(
        name="Typing",
        version="1.0",
        description="Имитация вечного набора сообщения",
        commands={
            "tp": _tp,
        },
        examples=[
            "`.tp` – имитировать набор сообщения в этом чате",
            "`.tp off` – прекратить печатать"
        ],
    )