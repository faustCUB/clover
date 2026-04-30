import os
import json
import hashlib
import asyncio
import requests
from modules.base import BaseModule
from utils import logger


MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
VT_DIR = os.path.join(MODULE_DIR, "VirusTotal")
TOKENS_FILE = os.path.join(VT_DIR, "tokens.json")

os.makedirs(VT_DIR, exist_ok=True)


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
        logger.error(f"Ошибка сохранения токенов VirusTotal: {e}")


async def _vttoken(event):
    raw = event.raw_text.strip().split(maxsplit=1)
    if len(raw) < 2 or not raw[1].strip():
        await event.edit("❌ Укажи токен: `.vttoken <токен>`\n\nПолучить токен: https://www.virustotal.com/gui/my-apikey")
        return

    token = raw[1].strip()
    tokens = _load_tokens()

    if token in tokens:
        await event.edit("⚠️ Этот токен уже добавлен")
        return

    tokens.append(token)
    _save_tokens(tokens)
    logger.success(f"Добавлен новый VirusTotal токен (всего: {len(tokens)})")
    await event.edit(f"✅ Токен добавлен. Всего токенов: **{len(tokens)}**")


async def _vt(event):
    tokens = _load_tokens()
    if not tokens:
        await event.edit(
            "❌ Нет токенов VirusTotal.\n\n"
            "Добавь токен командой `.vttoken <токен>`\n"
            "Получить токен: https://www.virustotal.com/gui/my-apikey"
        )
        return

    if not event.is_reply:
        await event.edit("❌ **Ответь на сообщение с файлом**")
        return

    reply = await event.get_reply_message()
    if not reply or not reply.file:
        await event.edit("❌ **В сообщении должен быть файл**")
        return

    await event.edit("🍀 **Скачиваю файл для проверки...**")

    file_path = None
    try:
        file_path = await event.client.download_media(reply)

        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        file_hash = sha256.hexdigest()

        loop = asyncio.get_event_loop()

        r = None
        used_token = None
        for token in tokens:
            headers = {"x-apikey": token}
            report_url = f"https://www.virustotal.com/api/v3/files/{file_hash}"
            resp = await loop.run_in_executor(None, lambda: requests.get(report_url, headers=headers, timeout=20))
            if resp.status_code == 429:
                logger.warning(f"VirusTotal токен исчерпан, пробую следующий...")
                continue
            r = resp
            used_token = token
            break

        if r is None:
            await event.edit(
                "❌ Все токены VirusTotal исчерпали квоту.\n\n"
                "Добавь новый токен: `.vttoken <токен>`\n"
                "Получить токен: https://www.virustotal.com/gui/my-apikey"
            )
            return

        headers = {"x-apikey": used_token}
        report_url = f"https://www.virustotal.com/api/v3/files/{file_hash}"

        if r.status_code == 404:
            await event.edit("🍀 **Файл не найден в базе. Загружаю на VirusTotal...**")

            def _upload():
                with open(file_path, "rb") as f:
                    return requests.post(
                        "https://www.virustotal.com/api/v3/files",
                        headers=headers,
                        files={"file": f},
                        timeout=90
                    )

            upload = await loop.run_in_executor(None, _upload)

            if upload.status_code not in (200, 202):
                await event.edit(f"❌ **Ошибка загрузки файла:** `{upload.status_code}`")
                return

            await event.edit("🍀 **Файл загружен. Ожидаю результат анализа...**")

            for _ in range(10):
                await asyncio.sleep(10)
                r = await loop.run_in_executor(None, lambda: requests.get(report_url, headers=headers, timeout=20))
                if r.status_code == 200:
                    break
            else:
                await event.edit("❌ **Отчёт не готов. Попробуй позже.**")
                return

        if r.status_code != 200:
            await event.edit(f"❌ **Ошибка VirusTotal:** `{r.status_code}`")
            return

        data = r.json().get("data", {}).get("attributes", {})
        stats = data.get("last_analysis_stats", {})
        results = data.get("last_analysis_results", {})

        malicious = stats.get("malicious", 0)
        suspicious = stats.get("suspicious", 0)
        undetected = stats.get("undetected", 0)

        msg = (
            f"🛡 **VirusTotal Analysis**\n\n"
            f"🔴 Вредоносных: `{malicious}`\n"
            f"🟠 Подозрительных: `{suspicious}`\n"
            f"🟢 Не обнаружено: `{undetected}`\n\n"
        )

        detected = []
        for engine, res in results.items():
            category = res.get("category", "")
            result = res.get("result") or "—"
            if category in ("malicious", "suspicious"):
                detected.append(f"• `{engine}` > {result}")

        if detected:
            msg += "**🚨 Детали обнаружения:**\n" + "\n".join(detected[:15])
            if len(detected) > 15:
                msg += f"\n_...и ещё {len(detected) - 15}_"
        else:
            msg += "**✅ Угроз не обнаружено.**"

        await event.edit(msg)
        logger.success(f"VirusTotal: файл проверен (Detections: {malicious})")

    except Exception as e:
        logger.error(f"Ошибка в модуле VirusTotal: {e}")
        await event.edit(f"❌ **Критическая ошибка:** `{e}`")
    finally:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)


def setup() -> BaseModule:
    return BaseModule(
        name="VirusTotal",
        version="1.0",
        description="Проверка файлов на вирусы через VirusTotal",
        commands={
            "vt": _vt,
            "vttoken": _vttoken,
        },
        examples=[
            "`.vt` (в ответ на файл) — проверить на вирусы",
            "`.vttoken <токен>` — добавить токен VirusTotal (virustotal.com/gui/my-apikey)",
        ],
    )
