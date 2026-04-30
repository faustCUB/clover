import asyncio
import re
from modules.base import BaseModule
from utils import logger


_tasks = {}
_targets = set()
_private = set()
_counters = {}


async def _mention(event):
    await event.delete()

    raw = (event.raw_text.strip().split(maxsplit=1)[1] if len(event.raw_text.strip().split()) > 1 else "").strip()

    if raw.lower() == "off":
        stopped = len(_targets) + len(_private)
        for task in _tasks.values():
            if not task.done():
                task.cancel()

        total_mentions = sum(_counters.values())
        _targets.clear()
        _private.clear()
        _tasks.clear()

        logger.success(f"Все упоминания остановлены. Чатов: {stopped}, всего: {logger.accent(total_mentions)}")
        return

    chat_id = event.chat_id
    is_private = event.is_private
    user = None
    custom_text = None

    if raw:
        match = re.match(r'^(@[\w\d_]+)(?:\s+(.+))?$', raw)
        if match:
            username = match.group(1)
            custom_text = match.group(2)
            try:
                user = await event.client.get_entity(username)
            except Exception:
                logger.error("Mention: пользователь не найден")
                return
        else:
            custom_text = raw

    if not user and event.is_reply:
        try:
            reply = await event.get_reply_message()
            user = await reply.get_sender()
        except Exception:
            logger.error("Mention: не удалось получить пользователя из реплая")
            return

    if not user:
        logger.error("Mention: не указан пользователь")
        return

    name = (user.first_name or "") + (" " + user.last_name if user.last_name else "")
    if not name.strip():
        name = user.username or "User"

    mention_text = f"[{name.strip()}](tg://user?id={user.id})"
    if custom_text:
        mention_text += f" {custom_text}"

    user_key = f"{user.id}_{chat_id}"
    task_key = f"{chat_id}_{user.id}"

    if (is_private and chat_id in _private) or (not is_private and chat_id in _targets):
        if task_key in _tasks:
            _tasks[task_key].cancel()

        if is_private:
            _private.discard(chat_id)
        else:
            _targets.discard(chat_id)

        logger.info(f"Mention остановлен для {user.id}, отправлено: {_counters.get(user_key, 0)}")
        return

    _counters[user_key] = 0
    if is_private:
        _private.add(chat_id)
    else:
        _targets.add(chat_id)

    async def mention_loop():
        try:
            while True:
                if (is_private and chat_id not in _private) or (not is_private and chat_id not in _targets):
                    break
                try:
                    msg = await event.client.send_message(chat_id, mention_text)
                    _counters[user_key] += 1
                    await msg.delete()
                    await asyncio.sleep(0.5)
                except Exception:
                    await asyncio.sleep(5)
        except asyncio.CancelledError:
            pass
        finally:
            _tasks.pop(task_key, None)

    _tasks[task_key] = asyncio.create_task(mention_loop())
    status = "в ЛС" if is_private else "в группе"
    logger.success(f"Запущено упоминание {logger.accent(name)} {status}")


def setup() -> BaseModule:
    return BaseModule(
        name="Mention",
        version="1.0",
        description="Спам-упоминание",
        commands={
            "mention": _mention,
        },
        examples=[
            "'.mention @username' – начать упоминать пользователя",
            "'.mention @username привет' – упоминать с текстом «привет»",
            "`.mention` (реплаем) – упоминать автора сообщения",
            "`.mention off` – выключить все активные упоминание"
        ],
    )