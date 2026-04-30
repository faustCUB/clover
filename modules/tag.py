import random
import asyncio
from telethon import events, utils
from telethon.tl.types import ChannelParticipantsSearch

from modules.base import BaseModule
from utils import logger


async def _tag_users(event):

    args = event.raw_text.strip().split(maxsplit=1)
    if len(args) < 2:
        await event.edit("❌ **Использование:** `.tag all` или `.tag 5`")
        return

    mode = args[1].lower()
    chat = await event.get_input_chat()

    try:
        await event.edit("🍀**Собираю список участников...**")
        
        participants = []
        async for user in event.client.iter_participants(
            chat, 
            filter=ChannelParticipantsSearch('')
        ):
            if user.bot or user.deleted:
                continue
            participants.append(user)

        if not participants:
            await event.edit("❌ В чате не найдено участников для упоминания.")
            return

        if mode == "all":
            users_to_tag = participants
        elif mode.isdigit():
            count = int(mode)
            if count <= 0:
                await event.edit("❌ Число должно быть больше нуля.")
                return
            users_to_tag = random.sample(participants, min(count, len(participants)))
        else:
            await event.edit("❌ Неверный формат. Используйте `all` или число.")
            return

        await event.delete()

        mentions = [
            f"[{utils.get_display_name(u)}](tg://user?id={u.id})"
            for u in users_to_tag
        ]

        chunk_size = 5
        for i in range(0, len(mentions), chunk_size):
            chunk = " ".join(mentions[i:i + chunk_size])
            await event.client.send_message(event.chat_id, chunk)
            await asyncio.sleep(1.5)
            
        logger.success(f"Упомянуто {len(users_to_tag)} участников в чате {event.chat_id}")

    except Exception as e:
        logger.error(f"Ошибка в модуле Tag: {e}")
        await event.respond(f"❌ **Ошибка:** `{str(e)[:100]}`")


def setup() -> BaseModule:
    return BaseModule(
        name="Tag",
        version="1.0",
        description="Упоминание участников чата",
        commands={
            "tag": _tag_users,
        },
        examples=[
            "`.tag all` – тегнуть всех",
            "`.tag 10` – тегнуть 10 случайных человек"
        ],
    )
