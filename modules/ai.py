import asyncio
import base64
import json
import mimetypes
import os
from collections import deque

import aiohttp
from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument
from modules.base import BaseModule
from utils import logger


MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
AI_DIR = os.path.join(MODULE_DIR, "ai")
SETTINGS_FILE = os.path.join(AI_DIR, "settings.json")
TOKENS_FILE = os.path.join(AI_DIR, "tokens.json")

os.makedirs(AI_DIR, exist_ok=True)


def _load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"prompt": None, "temperature": 0.75}


def _save_settings():
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(_ai.settings, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка сохранения настроек AI: {e}")


def _load_tokens() -> list:
    if os.path.exists(TOKENS_FILE):
        try:
            with open(TOKENS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except Exception:
            pass
    return []


def _save_tokens(tokens: list):
    try:
        with open(TOKENS_FILE, "w", encoding="utf-8") as f:
            json.dump(tokens, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка сохранения токенов AI: {e}")


async def _aitoken(event):
    raw = event.raw_text.strip().split(maxsplit=1)
    if len(raw) < 2 or not raw[1].strip():
        await event.edit("❌ Укажи токен: `.aitoken <токен>`\n\nПолучить токен: https://aistudio.google.com/apikey")
        return

    token = raw[1].strip()
    tokens = _load_tokens()

    if token in tokens:
        await event.edit("⚠️ Этот токен уже добавлен")
        return

    tokens.append(token)
    _save_tokens(tokens)
    _ai.GEMINI_TOKENS = tokens
    _ai.current_token_index = 0

    logger.success(f"Добавлен новый Gemini токен (всего: {len(tokens)})")
    await event.edit(f"✅ Токен добавлен. Всего токенов: **{len(tokens)}**")


async def _ai(event):
    tokens = _load_tokens()
    if not tokens:
        await event.reply(
            "❌ Нет токенов Gemini.\n\n"
            "Добавь токен командой `.aitoken <токен>`\n"
            "Получить токен: https://aistudio.google.com/apikey"
        )
        return

    _ai.GEMINI_TOKENS = tokens

    raw = event.raw_text.strip().split(maxsplit=1)
    args = raw[1].strip() if len(raw) > 1 else ""

    if args.lower().startswith("prompt"):
        rest = args[6:].strip()
        if not rest:
            current = _ai.settings.get("prompt") or "не установлен"
            await event.reply(f"Текущий промпт: {current}")
            return
        if rest.lower() == "off":
            _ai.settings["prompt"] = None
            _save_settings()
            logger.success("AI промпт удалён")
        else:
            _ai.settings["prompt"] = rest
            _save_settings()
            logger.success(f"AI промпт установлен: {rest}")
        await event.delete()
        return

    if args.lower().startswith("temperature"):
        rest = args[11:].strip()
        if not rest:
            current = _ai.settings.get("temperature", 0.75)
            await event.reply(f"Текущая температура: {current}")
            return
        try:
            val = float(rest)
            if not (0.0 <= val <= 2.0):
                raise ValueError
            _ai.settings["temperature"] = val
            _save_settings()
            logger.success(f"AI температура установлена: {val}")
        except ValueError:
            logger.error("AI: температура должна быть числом от 0.0 до 2.0")
        await event.delete()
        return

    user_text = args
    model = "gemini-2.5-flash"
    status = await event.reply(f"🍀 Думаю... `{model}`")

    chat_id = event.chat_id
    if chat_id not in _ai.history:
        _ai.history[chat_id] = deque(maxlen=20)

    image_data = None
    replied_text = None

    if event.is_reply:
        reply = await event.get_reply_message()
        if reply:
            if reply.media:
                is_image = False
                if isinstance(reply.media, MessageMediaPhoto):
                    is_image = True
                elif isinstance(reply.media, MessageMediaDocument):
                    if reply.document and reply.document.mime_type and reply.document.mime_type.startswith('image/'):
                        is_image = True

                if is_image:
                    try:
                        file_bytes = await event.client.download_media(reply.media, bytes)
                        mime_type = mimetypes.guess_type("image.jpg")[0] or "image/jpeg"
                        image_data = {
                            "inline_data": {
                                "mime_type": mime_type,
                                "data": base64.b64encode(file_bytes).decode("utf-8")
                            }
                        }
                    except Exception as e:
                        logger.error(f"Ошибка скачивания изображения: {e}")
                        await status.edit("❌ Не удалось скачать изображение.")
                        return
                else:
                    await status.edit("❌ Я могу отвечать только на текстовые сообщения или изображения.")
                    return

            if reply.text:
                replied_text = reply.text.strip()

    prompt_text = user_text
    if replied_text:
        if image_data:
            prompt_text = f"{replied_text}\n\n{prompt_text}" if prompt_text else replied_text
        else:
            if prompt_text:
                prompt_text = f"Сообщение, на которое я отвечаю:\n{replied_text}\n\nМой запрос: {prompt_text}"
            else:
                prompt_text = replied_text

    current_parts = []
    if prompt_text:
        current_parts.append({"text": prompt_text})
    if image_data:
        current_parts.append(image_data)
    if not current_parts:
        current_parts.append({"text": "Привет"})

    all_tokens = _ai.GEMINI_TOKENS
    for attempt in range(len(all_tokens)):
        token = all_tokens[_ai.current_token_index % len(all_tokens)]
        _ai.current_token_index = (_ai.current_token_index + 1) % len(all_tokens)

        try:
            contents = list(_ai.history[chat_id])
            contents.append({"role": "user", "parts": current_parts})

            system_instruction = None
            if _ai.settings.get("prompt"):
                system_instruction = {"parts": [{"text": _ai.settings["prompt"]}]}

            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={token}"

            payload = {
                "contents": contents,
                "generationConfig": {
                    "temperature": _ai.settings.get("temperature", 0.75),
                    "maxOutputTokens": 4096
                }
            }

            if system_instruction:
                payload["systemInstruction"] = system_instruction

            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=90) as resp:
                    response_text = await resp.text()

                    if resp.status in (429, 503):
                        logger.warn(f"Токен заблокирован (код {resp.status}), пробую следующий...")
                        await asyncio.sleep(0.3)
                        continue

                    if resp.status != 200:
                        logger.error(f"API error {resp.status}: {response_text[:300]}")
                        if attempt == len(all_tokens) - 1:
                            await status.edit(f"❌ Все токены вернули ошибку ({resp.status})")
                        continue

                    data = await resp.json()
                    answer = data["candidates"][0]["content"]["parts"][0]["text"].strip()

                    _ai.history[chat_id].append({"role": "user", "parts": current_parts})
                    _ai.history[chat_id].append({"role": "model", "parts": [{"text": answer}]})

                    if len(answer) > 3800:
                        await status.edit(answer[:3800] + "\n...")
                        await asyncio.sleep(0.6)
                        await status.reply(answer[3800:])
                    else:
                        await status.edit(answer)

                    logger.success(f"Gemini ответил с токена #{_ai.current_token_index} ({model})")
                    return

        except asyncio.TimeoutError:
            logger.warn(f"Таймаут токена {attempt + 1}")
            continue
        except Exception as e:
            logger.error(f"Ошибка с токеном {attempt + 1}: {e}")
            continue

    await status.edit(
        "❌ Все токены Gemini исчерпали квоту или недоступны.\n\n"
        "Добавь новый токен: `.aitoken <токен>`\n"
        "Получить токен: https://aistudio.google.com/apikey"
    )


_ai.GEMINI_TOKENS = []
_ai.history = {}
_ai.current_token_index = 0
_ai.settings = _load_settings()


def setup() -> BaseModule:
    return BaseModule(
        name="Ai",
        version="1.0",
        description="Google Gemini ИИ",
        commands={
            "ai": _ai,
            "aitoken": _aitoken,
        },
        examples=[
            "`.ai Объясни анатомию мопсов` – задать вопрос",
            "`.ai` (реплаем на текст) – ответить на чужое сообщение",
            "`.ai` (реплаем на фото) – описать или обсудить изображение",
            "`.ai prompt отвечай только на русском и коротко` – установить системный промпт",
            "`.ai prompt` – посмотреть текущий промпт",
            "`.ai prompt off` – удалить системный промпт",
            "`.ai temperature 0.2` – точные и сухие ответы (0.0–2.0, по умолчанию 0.75)",
            "`.ai temperature 1.5` – креативные и разнообразные ответы",
            "`.ai temperature` – посмотреть текущую температуру",
            "`.aitoken <токен>` – добавить токен Google AI Studio",
        ],
    )
