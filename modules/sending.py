import asyncio
import random
from telethon import errors
from modules.base import BaseModule
from utils import logger

_rs_task = None
_rs_config = {}


async def _sending_loop(client):
    try:
        while True:
            chat_ids = _rs_config.get("chat_ids", [])
            msg = _rs_config.get("reply")
            interval = _rs_config.get("interval", 60)

            for chat_id in chat_ids:
                try:
                    if msg.media:
                        await client.send_file(
                            chat_id,
                            msg.media,
                            caption=msg.text or ""
                        )
                    else:
                        await client.send_message(chat_id, msg.text or "")
                    
                    logger.info(f"Рассылка: отправлено в {logger.accent(str(chat_id))}")

                except errors.FloodWaitError as e:
                    logger.warn(f"FloodWait: ожидание {e.seconds} сек.")
                    await asyncio.sleep(e.seconds + 2)
                except Exception as e:
                    logger.error(f"Ошибка отправки в {chat_id}: {e}")

            jitter = random.randint(-3, 3)
            sleep_time = max(1, interval + jitter)
            await asyncio.sleep(sleep_time)

    except asyncio.CancelledError:
        logger.info("Задача рассылки остановлена")
    except Exception as e:
        logger.error(f"Критическая ошибка в цикле рассылки: {e}")


async def _sending_control(event):
    global _rs_task, _rs_config
    logger.info(f"Команда {logger.accent('.send')} вызвана")
    
    args_text = event.raw_text.strip().split(maxsplit=1)
    if len(args_text) < 2:
        await event.edit("❌ Используйте `.send off` для остановки рассылки.")
        return

    params = args_text[1].split()
    action = params[-1].lower()

    if action == "off":
        if _rs_task:
            _rs_task.cancel()
            _rs_task = None
            await event.edit("🍀 **Рассылка успешно остановлена**")
            logger.success("Рассылка остановлена пользователем")
        else:
            await event.edit("⚠️ **Рассылка не запущена**")
        return

    if action != "on":
        await event.edit("❌ Последний аргумент должен быть `on` или `off`.")
        return

    try:
        if len(params) < 3:
            raise ValueError
        chat_ids = [int(cid.strip()) for cid in params[0].split(",") if cid.strip()]
        interval = int(params[1])
    except Exception:
        await event.edit("❌ **Ошибка формата!**\nИспользуйте: `.send ID,ID интервал on`")
        return

    if interval <= 0:
        await event.edit("❌ Интервал должен быть больше 0 секунд.")
        return

    reply = await event.get_reply_message()
    if not reply:
        await event.edit("❌ **Ошибка:** Вы должны ответить командой на сообщение для рассылки!")
        return

    if _rs_task:
        _rs_task.cancel()

    _rs_config = {
        "chat_ids": chat_ids,
        "interval": interval,
        "reply": reply
    }

    await event.edit(
        f"🍀 **Рассылка запущена!**\n\n"
        f" **Чатов:** `{len(chat_ids)}`\n"
        f" **Интервал:** `{interval}` сек.\n"
        f" **Тип:** `{'Медиа' if reply.media else 'Текст'}`"
    )
    logger.success(f"Запуск рассылки на {len(chat_ids)} чатов")

    _rs_task = asyncio.create_task(_sending_loop(event.client))


def setup() -> BaseModule:
    return BaseModule(
        name="Sending",
        version="1.0",
        description="Рассылка сообщений",
        commands={
            "send": _sending_control,
        },
        examples=[
            "`.send -100123456789 60 on` (в ответ на сообщение) – рассылка сообщения в чат",
            "`.send -100123, -100456 300 on`  (в ответ на сообщение) – рассылка сообщения в несколько чатов",
            "`.send off` – выключить рассылку"
        ],
    )
