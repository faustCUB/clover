import asyncio
from telethon import events
from telethon.errors import FloodWaitError
from modules.base import BaseModule
from utils import logger

_spam_tasks = {}


async def _spam(event):
    
    args = event.raw_text.strip().split(maxsplit=2)

    chat_id = event.chat_id

    if len(args) > 1 and args[1].lower() == "off":
        task = _spam_tasks.get(chat_id)
        if task and not task.done():
            task.cancel()
            _spam_tasks.pop(chat_id, None)
            await event.edit("🛑 **Спам остановлен**")
            logger.success(f"Спам в чате {chat_id} остановлен")
        else:
            await event.edit("❌ **В этом чате нет активного спама**")
        return

    if chat_id in _spam_tasks and not _spam_tasks[chat_id].done():
        await event.edit("⚠️ **Спам уже запущен.** Остановите его через `.spam off`")
        return

    count = None
    text = None
    
    if len(args) > 1:
        if args[1].isdigit():
            count = int(args[1])
            if len(args) > 2:
                text = args[2]
        else:
            text = args[1] + (f" {args[2]}" if len(args) > 2 else "")

    reply = await event.get_reply_message()

    if not text and not reply:
        await event.edit("❌ **Ошибка:** Укажите текст или ответьте на сообщение.")
        return

    if count is not None:
        count = min(count, 1000)
    
    infinite = count is None
    await event.delete()

    async def do_spam():
        sent = 0
        try:
            while infinite or sent < count:
                try:
                    if text:
                        await event.client.send_message(chat_id, text)
                    elif reply:
                        if reply.media:
                            await event.client.send_file(
                                chat_id,
                                file=reply.media,
                                caption=reply.text or ""
                            )
                        else:
                            await event.client.send_message(chat_id, reply.text or "")
                    
                    sent += 1

                    await asyncio.sleep(0.15 if text else 0.3)

                except FloodWaitError as e:
                    logger.warn(f"FloodWait: ожидание {e.seconds} сек.")
                    await asyncio.sleep(e.seconds + 1)
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    logger.error(f"Ошибка при спаме: {e}")
                    await asyncio.sleep(1)

        except asyncio.CancelledError:
            pass
        finally:
            _spam_tasks.pop(chat_id, None)
            logger.info(f"Спам завершен: отправлено {sent} сообщений в {chat_id}")

    task = asyncio.create_task(do_spam())
    _spam_tasks[chat_id] = task


def setup() -> BaseModule:
    return BaseModule(
        name="Spam",
        version="1.0",
        description="Спамер",
        commands={
            "spam": _spam,
        },
        examples=[
            "`.spam 10 Текст` – отправить 10 сообщений",
            "`.spam Текст` – бесконечный спам текстом",
            "`.spam 15` (в ответ на медиа) – спам файлом",
            "`.spam off` – остановить спам в текущем чате"
        ],
    )
