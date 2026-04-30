import asyncio

from telethon import events

from modules.base import BaseModule
from utils import logger


async def _d(event):
    if not event.is_reply:
        await event.edit("❌ Ответьте на сообщение, которое хотите удалить.")
        return

    reply = await event.get_reply_message()
    if not reply:
        await event.edit("❌ Сообщение не найдено.")
        return

    await event.delete()

    if reply.out:
        await reply.delete()
        logger.success(f"Удалено своё сообщение в чате {event.chat_id}")
        return

    try:
        me = await event.client.get_me()
        perms = await event.client.get_permissions(event.chat_id, me)

        if perms.delete_messages:
            await reply.delete()
            logger.success(f"Удалено чужое сообщение в чате {event.chat_id}")
        else:
            await event.respond("❌ Недостаточно прав для удаления чужого сообщения.")
            logger.warn(f"Нет прав на удаление сообщений в чате {event.chat_id}")
    except Exception as e:
        logger.error(f"Ошибка при удалении чужого сообщения: {e}")
        await event.respond(f"❌ Ошибка: {str(e)[:100]}")


async def _d_range(event):

    if not event.is_reply:
        await event.edit("❌ Ответьте на сообщение, откуда начинать удаление.")
        return

    reply = await event.get_reply_message()
    if not reply:
        await event.edit("❌ Сообщение не найдено.")
        return

    direction = event.raw_text.strip().split()[-1].lower()
    anchor_id = reply.id

    await event.delete()
    await _delete_range(event, anchor_id, direction)


async def _dl(event):
    await event.delete()

    me = await event.client.get_me()
    deleted = 0
    errors = 0

    logger.info(f"Запущено удаление всех своих сообщений в чате {event.chat_id}")

    try:
        async for msg in event.client.iter_messages(event.chat_id, from_user=me.id):
            try:
                await msg.delete()
                deleted += 1
                if deleted % 50 == 0:
                    logger.info(f"Прогресс dl: удалено {deleted} сообщений")
                await asyncio.sleep(0.01)
            except Exception:
                errors += 1
                continue
    except Exception as e:
        logger.error(f"Ошибка итерации при dl: {e}")

    logger.success(f"dl завершён — удалено: {deleted}, ошибок: {errors}")


async def _delete_range(event, anchor_id: int, direction: str):
    collected = []
    total = 0

    logger.info(f"Запущено удаление сообщений {direction} от anchor={anchor_id}")

    try:
        if direction == "up":
            iterator = event.client.iter_messages(
                event.chat_id,
                offset_id=anchor_id,
            )
        else:
            iterator = event.client.iter_messages(
                event.chat_id,
                min_id=anchor_id,
                reverse=True,
            )

        async for msg in iterator:
            collected.append(msg.id)

            if len(collected) >= 100:
                try:
                    await event.client.delete_messages(event.chat_id, collected)
                    total += len(collected)
                    logger.info(f"d {direction}: удалено {total} сообщений")
                except Exception as e:
                    logger.warn(f"Не удалось удалить батч: {e}")
                collected.clear()
                await asyncio.sleep(0.05)

        if collected:
            try:
                await event.client.delete_messages(event.chat_id, collected)
                total += len(collected)
            except Exception as e:
                logger.warn(f"Не удалось удалить остаток: {e}")

    except Exception as e:
        logger.error(f"Ошибка при удалении диапазона {direction}: {e}")

    logger.success(f"d {direction} завершён – всего удалено: {total} сообщений")


def setup() -> BaseModule:
    return BaseModule(
        name="Delete",
        version="1.0",
        description="Удаление сообщений",
        commands={
            "d up": _d_range,
            "d down": _d_range,
            "d": _d,
            "dl": _dl,
        },
        examples=[
            "`.d` – удалить сообщение (по реплаю)",
            "`.d up` – удалить все сообщения выше реплая",
            "`.d down` – удалить все сообщения ниже реплая",
            "`.dl` – удалить все свои сообщения в чате",
        ],
    )
