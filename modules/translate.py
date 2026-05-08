import requests
from modules.base import BaseModule
from utils import logger

LANG_MAP = {"ru": "ru", "ua": "uk", "kz": "kk"}
LANG_NAMES = {"ru": "🇷🇺 Русский", "ua": "🇺🇦 Украинский", "kz": "🇰🇿 Казахский"}


def _translate(text: str, target: str) -> str:
    url = "https://translate.googleapis.com/translate_a/single"
    params = {
        "client": "gtx",
        "sl": "auto",
        "tl": target,
        "dt": "t",
        "q": text,
    }
    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()
    data = response.json()
    return "".join(part[0] for part in data[0] if part[0])


async def _tr(event):
    args = event.raw_text.strip().split(maxsplit=1)

    if len(args) < 2 or args[1].lower() not in LANG_MAP:
        await event.edit("❌ Укажи язык: `.tr ru` / `.tr ua` / `.tr kz`")
        return

    lang = args[1].lower()
    reply = await event.get_reply_message()

    if not reply or not reply.text:
        await event.edit("❌ Ответь на сообщение которое нужно перевести")
        return

    await event.edit("🍀 Перевожу...")

    try:
        translated = _translate(reply.text, LANG_MAP[lang])
        await event.edit(f"{LANG_NAMES[lang]}:\n{translated}")
        logger.success(f"Перевод на {logger.accent(lang)} выполнен")
    except Exception as e:
        await event.edit(f"❌ Ошибка: `{e}`")
        logger.error(f"Ошибка .tr: {e}")


def setup() -> BaseModule:
    return BaseModule(
        name="Translate",
        version="1.0",
        description="Переводчик",
        commands={
            "tr": _tr,
        },
        examples=["`.tr ru` — перевести на русский", "`.tr ua` — перевести на украинский", "`.tr kz` — перевести на казахский"],
    )
