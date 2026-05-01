import asyncio
import os
import re
import time
from modules.base import BaseModule
from utils import logger


MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
_DOWNLOAD_DIR = os.path.join(MODULE_DIR, "soundcloud")


class _SilentLogger:
    def debug(self, msg): pass
    def info(self, msg): pass
    def warning(self, msg): pass
    def error(self, msg): pass


async def _sc(event):
    try:
        from yt_dlp import YoutubeDL
    except ImportError:
        await event.edit("❌ **Ошибка:** `yt-dlp` не установлен.\nУстановите: `pip install yt-dlp`")
        return

    raw = event.raw_text.strip().split(maxsplit=1)
    url = None

    if len(raw) > 1:
        url = _extract_url(raw[1])

    if not url:
        reply = await event.get_reply_message()
        if reply:
            url = _extract_url(reply.text or "")

    if not url:
        await event.edit("❌ Укажите ссылку или ответьте на сообщение со ссылкой.")
        return

    if "soundcloud.com" not in url:
        await event.edit("❌ Ссылка должна быть с SoundCloud.")
        return

    os.makedirs(_DOWNLOAD_DIR, exist_ok=True)
    await event.edit("🍀 **Получение информации...**")

    info_opts = {
        "quiet": True,
        "no_warnings": True,
        "logger": _SilentLogger(),
    }

    def _get_info():
        with YoutubeDL(info_opts) as ydl:
            return ydl.extract_info(url, download=False)

    try:
        loop = asyncio.get_event_loop()
        info = await loop.run_in_executor(None, _get_info)
    except Exception as e:
        logger.error(f"SoundCloud Info Error: {e}")
        await event.edit(f"❌ **Ошибка получения информации:** `{e}`")
        return

    title = _safe_name(info.get("title", "track"))

    await event.edit(f"🍀 **Загрузка...**\n`{title}`")

    a_path_tpl = os.path.join(_DOWNLOAD_DIR, f"{title} (CloverUserBot).%(ext)s")
    a_path_final = os.path.join(_DOWNLOAD_DIR, f"{title} (CloverUserBot).mp3")

    a_opts = {
        "format": "bestaudio/best",
        "outtmpl": a_path_tpl,
        "quiet": True,
        "no_warnings": True,
        "logger": _SilentLogger(),
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
    }

    try:
        await loop.run_in_executor(None, lambda: YoutubeDL(a_opts).download([url]))
    except Exception as e:
        logger.error(f"SoundCloud Download Error: {e}")
        await event.edit(f"❌ **Ошибка загрузки:** `{e}`")
        return

    if not os.path.exists(a_path_final):
        await event.edit("❌ **Файл не найден после загрузки.**")
        return

    await event.edit(f"🍀 **Отправка...**\n`{title}`")

    try:
        await event.client.send_file(
            event.chat_id, a_path_final,
            reply_to=event.reply_to_msg_id
        )
        os.remove(a_path_final)
        logger.success(f"SoundCloud: отправлен трек '{title}'")
    except Exception as e:
        logger.error(f"SoundCloud Send Error: {e}")
        await event.edit(f"❌ **Ошибка отправки:** `{e}`")
        return

    await event.edit("✅ **Готово.**")
    await asyncio.sleep(3)
    await event.delete()


def _extract_url(text: str) -> str | None:
    urls = re.findall(r"https?://\S+", text or "")
    return urls[0] if urls else None


def _safe_name(name: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "", name)[:50]


def setup() -> BaseModule:
    return BaseModule(
        name="SoundCloud",
        version="1.0",
        description="Загрузка треков с SoundCloud",
        commands={
            "sc": _sc,
        },
        examples=[
            "`.sc <ссылка>` — скачать трек с SoundCloud",
            "`.sc` (в ответ на сообщение со ссылкой) — скачать трек",
        ],
    )