import asyncio
import os
import re
import tempfile
import requests
from modules.base import BaseModule
from utils import logger

_API = "https://tikwm.com/api/"
_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
_TIMEOUT = 15


async def _tt(event):
    
    args = event.raw_text.strip().split(maxsplit=1)
    url = None

    if len(args) > 1:
        url = _extract_url(args[1])
    
    if not url:
        reply = await event.get_reply_message()
        if reply:
            url = _extract_url(reply.text or "")

    if not url or "tiktok.com" not in url:
        await event.edit(
            "🍀 **TikTok Downloader**\n\n"
            "`.tt <url>` — прямая ссылка\n"
            "`.tt` — ответ на сообщение со ссылкой\n\n"
        )
        return

    await event.edit("🍀 **Получение информации...**")
    
    data = await _fetch_api(url)
    if not data:
        await event.edit("❌ Не удалось получить данные. Проверь ссылку.")
        return

    images = data.get("images") or []
    video_url = data.get("play")
    music_url = data.get("music")
    sent_count = 0

    if images:
        await event.edit(f"🍀 **Загрузка слайд-шоу ({len(images)} фото)...**")
        files = []
        for img_url in images:
            path = await _download_file(img_url, ".jpg")
            if path:
                files.append(path)
        
        if files:
            await event.client.send_message(
                event.chat_id,
                file=files,
                message="🍀 **Слайд-шоу из TikTok**",
                reply_to=event.reply_to_msg_id
            )
            for f in files:
                if os.path.exists(f):
                    os.remove(f)
            sent_count += 1
        
        await event.delete()
        logger.success(f"TikTok: слайд-шоу отправлено ({len(files)} фото)")
        return

    if video_url:
        await event.edit("🍀 **Загрузка видео...**")
        path = await _download_file(video_url, ".mp4")
        if path:
            await event.client.send_message(
                event.chat_id,
                file=path,
                message="🍀 **Видео без водяного знака**",
                supports_streaming=True,
                reply_to=event.reply_to_msg_id
            )
            os.remove(path)
            sent_count += 1

    if music_url:
        await event.edit("🍀 **Загрузка аудио...**")
        path = await _download_file(music_url, ".mp3")
        if path:
            await event.client.send_message(
                event.chat_id,
                file=path,
                message="🍀 **Аудио из TikTok**",
                reply_to=event.reply_to_msg_id
            )
            os.remove(path)
            sent_count += 1

    if sent_count > 0:
        await event.edit(f"🍀 **Готово. Отправлено файлов: {sent_count}**")
        await asyncio.sleep(3)
        await event.delete()
        logger.success(f"TikTok: контент успешно загружен и отправлен")
    else:
        await event.edit("❌ Не удалось получить или отправить файлы.")
        logger.error("TikTok: не удалось обработать контент")


async def _fetch_api(url: str) -> dict | None:
    try:
        loop = asyncio.get_event_loop()
        resp = await loop.run_in_executor(None, lambda: requests.get(
            _API, params={"url": url}, headers=_HEADERS, timeout=_TIMEOUT
        ).json())
        
        if resp.get("code") != 0 or "data" not in resp:
            return None
        return resp["data"]
    except Exception as e:
        logger.error(f"TikTok API Error: {e}")
        return None


async def _download_file(url: str, ext: str) -> str | None:
    try:
        loop = asyncio.get_event_loop()
        content = await loop.run_in_executor(None, lambda: requests.get(
            url, headers=_HEADERS, timeout=_TIMEOUT
        ).content)
        
        if len(content) < 100:
            return None
            
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            tmp.write(content)
            return tmp.name
    except Exception as e:
        logger.error(f"TikTok Download Error: {e}")
        return None


def _extract_url(text: str) -> str | None:
    match = re.search(r"https?://[^\s]*tiktok\.com[^\s]*", text or "")
    return match.group(0) if match else None


def setup() -> BaseModule:
    return BaseModule(
        name="TikTok",
        version="1.0",
        description="Загрузка видео с TikTok без водянки",
        commands={
            "tt": _tt,
        },
        examples=["`.tt` <ссылка>", "`.tt` (в ответ на ссылку)"],
    )
