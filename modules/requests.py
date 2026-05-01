import asyncio
from telethon import errors
from telethon.tl.types import InputUserSelf
from telethon.tl.functions.messages import GetChatInviteImportersRequest, HideChatJoinRequestRequest
from modules.base import BaseModule
from utils import logger


async def _requests(event):
    args = event.raw_text.strip().split(maxsplit=1)

    if len(args) < 2:
        await event.edit("❌ Укажите ID канала. Пример: `.r -100123456789`")
        return

    try:
        chat_id = int(args[1])
    except ValueError:
        await event.edit("❌ Неверный ID канала.")
        return

    await event.edit("🍀 **Получение заявок...**")

    try:
        entity = await event.client.get_entity(chat_id)
    except Exception as e:
        await event.edit(f"❌ **Не удалось найти канал:** `{e}`")
        return

    accepted = 0
    errors_count = 0

    while True:
        try:
            result = await event.client(GetChatInviteImportersRequest(
                peer=entity,
                limit=100,
                requested=True,
                offset_date=0,
                offset_user=InputUserSelf()
            ))
        except errors.ChatAdminRequiredError:
            await event.edit("❌ **Нет прав для просмотра заявок.**")
            return
        except Exception as e:
            await event.edit(f"❌ **Ошибка получения заявок:** `{e}`")
            return

        if not result.importers:
            break

        for imp in result.importers:
            try:
                await event.client(HideChatJoinRequestRequest(
                    peer=entity,
                    user_id=imp.user_id,
                    approved=True
                ))
                accepted += 1
                logger.info(f"Requests: принят пользователь {logger.accent(str(imp.user_id))}")
            except errors.FloodWaitError as e:
                logger.warn(f"FloodWait: ожидание {e.seconds} сек.")
                await asyncio.sleep(e.seconds + 2)
            except Exception as e:
                logger.error(f"Ошибка принятия {imp.user_id}: {e}")
                errors_count += 1

        await asyncio.sleep(1)

    if accepted == 0:
        await event.edit("⚠️ **Заявок не найдено.**")
    else:
        await event.edit(
            f"✅ **Готово**\n\n"
            f"**Принято:** `{accepted}`\n"
            f"**Ошибок:** `{errors_count}`"
        )
        logger.success(f"Requests: принято {accepted} заявок")


def setup() -> BaseModule:
    return BaseModule(
        name="Requests",
        version="1.0",
        description="Принятие заявок в канал",
        commands={
            "r": _requests,
        },
        examples=[
            "`.r -100123456789` — принять все заявки в канал",
        ],
    )