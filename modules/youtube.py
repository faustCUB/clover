import asyncio
import os
import re
import time
from modules.base import BaseModule
from utils import logger


MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
_DOWNLOAD_DIR = os.path.join(MODULE_DIR, "youtube")


class _SilentLogger:
    def debug(self, msg): pass
    def info(self, msg): pass
    def warning(self, msg):
        if "No supported JavaScript runtime" in msg:
            return
        if "YouTube extraction without a JS runtime" in msg:
            return
    def error(self, msg): pass


async def _yt(event):
    
    try:
        from yt_dlp import YoutubeDL
    except ImportError:
        await event.edit("❌ **Ошибка:** `yt-dlp` не установлен.\nУстановите: `pip install yt-dlp`")
        return

    raw = event.raw_text.strip().split(maxsplit=2)
    mode = "both"
    url = None

    if len(raw) > 1:
        first_arg = raw[1].lower()
        if first_arg in ("video", "audio"):
            mode = first_arg
            if len(raw) > 2:
                url = _extract_url(raw[2])
        else:
            url = _extract_url(raw[1])

    if not url:
        reply = await event.get_reply_message()
        if reply:
            url = _extract_url(reply.text or "")

    if not url:
        await event.edit("❌ Укажите ссылку или ответьте на сообщение со ссылкой.")
        return

    os.makedirs(_DOWNLOAD_DIR, exist_ok=True)
    await event.edit("🍀 **Получение информации...**")

    info_opts = {
        "quiet": True,
        "no_warnings": True,
        "logger": _SilentLogger(),
        "extractor_args": {"youtube": {"player_client": ["android", "web"]}}
    }
    
    def _get_info():
        with YoutubeDL(info_opts) as ydl:
            return ydl.extract_info(url, download=False)

    try:
        loop = asyncio.get_event_loop()
        info = await loop.run_in_executor(None, _get_info)
    except Exception as e:
        logger.error(f"YouTube Info Error: {e}")
        await event.edit(f"❌ **Ошибка получения информации:** `{e}`")
        return

    title = _safe_name(info.get("title", "video"))
    sent_count = 0

    if mode in ("video", "both"):
        await event.edit(f"🍀 **Загрузка видео...**\n`{title}`")
        v_path = os.path.join(_DOWNLOAD_DIR, f"{title} (CloverUserBot).mp4")
        v_opts = {
            "format": "best[height<=720][ext=mp4]/best[height<=720]/best",
            "outtmpl": v_path,
            "quiet": True,
            "no_warnings": True,
            "logger": _SilentLogger(),
        }
        try:
            await loop.run_in_executor(None, lambda: YoutubeDL(v_opts).download([url]))
            if os.path.exists(v_path):
                await event.client.send_file(
                    event.chat_id, v_path,
                    supports_streaming=True,
                    reply_to=event.reply_to_msg_id
                )
                os.remove(v_path)
                sent_count += 1
        except Exception as e:
            logger.error(f"YouTube Video Download Error: {e}")

    if mode in ("audio", "both"):
        await event.edit(f"🍀 **Загрузка аудио...**\n`{title}`")
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
            if os.path.exists(a_path_final):
                await event.client.send_file(
                    event.chat_id, a_path_final,
                    reply_to=event.reply_to_msg_id
                )
                os.remove(a_path_final)
                sent_count += 1
        except Exception as e:
            logger.error(f"YouTube Audio Download Error: {e}")

    if sent_count > 0:
        await event.edit(f"✅ **Готово. Отправлено: {sent_count}**")
        await asyncio.sleep(3)
        await event.delete()
        logger.success(f"YouTube: успешно загружено {sent_count} файл(ов)")
    else:
        await event.edit("❌ **Не удалось загрузить или отправить контент.**")


def _extract_url(text: str) -> str | None:
    urls = re.findall(r"https?://\S+", text or "")
    return urls[0] if urls else None


def _safe_name(name: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "", name)[:50]


def setup() -> BaseModule:
    return BaseModule(
        name="YouTube",
        version="1.0",
        description="Загрузка видео и аудио с YouTube",
        commands={
            "yt": _yt,
        },
        examples=[
            "`.yt` <ссылка/ответ> — скачать видео и аудио",
            "`.yt video` <ссылка/ответ> — скачать видео",
            "`.yt audio` <ссылка/ответ> — скачать аудио"
        ],
    )