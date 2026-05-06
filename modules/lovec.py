import os
import re
import json
import time
from telethon import TelegramClient, events
from telethon.tl.types import Message, MessageEntityUrl, MessageEntityTextUrl
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.messages import ImportChatInviteRequest
from telethon.errors import UserAlreadyParticipantError, InviteHashExpiredError
from modules.base import BaseModule
from utils import logger

MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
LOVEC_DIR = os.path.join(MODULE_DIR, "lovec")
IGNORE_FILE = os.path.join(LOVEC_DIR, "lovec_ignore.json")
STATS_FILE = os.path.join(LOVEC_DIR, "lovec_stats.json")

os.makedirs(LOVEC_DIR, exist_ok=True)

_state = {"active": False}
_ignore_ids: set[int] = set()
_seen_codes: dict[str, float] = {}
_counted_ids: set[int] = set()
SEEN_TTL = 10.0

_stats = {"count": 0, "currencies": {}}

CHECK_PATTERN = re.compile(
    r"https?://(?:www\.)?t\.me/(?:CryptoBot|send)\?start=([A-Za-z0-9_\-]+)",
    re.IGNORECASE
)

RECEIVED_PATTERN = re.compile(
    r"([\d.,]+)\s*([A-Z]{2,10})",
    re.IGNORECASE
)


def _load_ignore():
    global _ignore_ids
    if os.path.exists(IGNORE_FILE):
        with open(IGNORE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            _ignore_ids = set(data.get("ignore", []))
    else:
        _ignore_ids = set()


def _save_ignore():
    with open(IGNORE_FILE, "w", encoding="utf-8") as f:
        json.dump({"ignore": list(_ignore_ids)}, f, indent=2)


def _load_stats():
    global _stats
    if os.path.exists(STATS_FILE):
        with open(STATS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if "total_usdt" in data and "currencies" not in data:
                _stats = {
                    "count": data.get("count", 0),
                    "currencies": {"USDT": data.get("total_usdt", 0.0)}
                }
            else:
                _stats = data
    else:
        _stats = {"count": 0, "currencies": {}}


def _save_stats():
    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(_stats, f, indent=2)


def _handle_received(text: str):
    amount = 0.0
    currency = "UNKNOWN"

    m = RECEIVED_PATTERN.search(text)
    if m:
        try:
            amount = float(m.group(1).replace(",", "."))
            currency = m.group(2).upper()
        except ValueError:
            pass

    _stats["count"] += 1
    if currency not in _stats["currencies"]:
        _stats["currencies"][currency] = 0.0
    _stats["currencies"][currency] = round(_stats["currencies"][currency] + amount, 8)
    _save_stats()

    logger.info(
        f"✅ +{amount} {currency} | "
        f"Итого: {_stats['count']} шт"
    )


async def _lovec_cmd(event):
    args = event.raw_text.strip().split()

    if len(args) > 1 and args[1].lower() == "ignore":
        sub = args[2].lower() if len(args) > 2 else None

        if sub == "clear":
            _ignore_ids.clear()
            _save_ignore()
            await event.edit("🗑️ **Список игнора полностью очищен.**")
            return

        elif sub in ["list", "ls"]:
            if not _ignore_ids:
                await event.edit("📋 Список игнора пуст.")
            else:
                ids = "\n".join(f"• `{iid}`" for iid in sorted(_ignore_ids))
                await event.edit(f"📋 **Игнорируемые ID:**\n{ids}")
            return

        else:
            try:
                target_id = int(args[2])
                _ignore_ids.add(target_id)
                _save_ignore()
                await event.edit(f"🚫 ID `{target_id}` добавлен в игнор.")
                return
            except (ValueError, IndexError):
                await event.edit("❌ Неверный ID.")
                return

    if len(args) > 1 and args[1].lower() == "stats":
        currencies_text = "\n".join(
            f"  • `{cur}`: `{val:.8f}`"
            for cur, val in _stats.get("currencies", {}).items()
        ) or "  • пусто"

        await event.edit(
            f"📊 **Статистика Чеков:**\n\n"
            f"• Чеков словлено: `{_stats['count']}`\n"
            f"• По валютам:\n{currencies_text}"
        )
        return

    if len(args) == 2:
        cmd = args[1].lower()
        if cmd == "on":
            _state["active"] = True
            await event.edit("🍀 Ловец **включён**")
        elif cmd == "off":
            _state["active"] = False
            await event.edit("🔴 Ловец **выключен**.")
        else:
            await event.edit(get_help_text())
        return

    await event.edit(get_help_text())


def get_help_text():
    return (
        "❓ **Неизвестная команда, напишите:**\n\n"
        "`.help lovec`"
    )


def _extract_all_urls(message: Message) -> str:
    urls = []

    if message.raw_text:
        urls.append(message.raw_text)

    if message.entities:
        for ent in message.entities:
            if isinstance(ent, MessageEntityTextUrl):
                if ent.url:
                    urls.append(ent.url)
            elif hasattr(ent, 'url') and ent.url and not isinstance(ent, MessageEntityUrl):
                urls.append(ent.url)

    if hasattr(message, 'reply_markup') and message.reply_markup:
        try:
            for row in message.reply_markup.rows:
                for button in row.buttons:
                    if hasattr(button, 'url') and button.url:
                        urls.append(button.url)
        except Exception:
            pass

    return " ".join(urls)


def _extract_channel_links(text: str) -> list[str]:
    all_links = re.findall(
        r"https?://(?:www\.)?t\.me/[A-Za-z0-9_+/\-]+",
        text,
        re.IGNORECASE
    )
    result = []
    for link in all_links:
        if re.search(r"t\.me/(?:CryptoBot|send)\?start=", link, re.IGNORECASE):
            continue
        result.append(link)
    return result


async def _join_channels(client: TelegramClient, links: list[str]):
    for link in links:
        try:
            invite_match = re.search(
                r"t\.me/(?:joinchat/|\+)([A-Za-z0-9_\-]+)",
                link,
                re.IGNORECASE
            )
            if invite_match:
                hash_ = invite_match.group(1)
                await client(ImportChatInviteRequest(hash_))
                logger.info(f"✅ Вступили: {link}")
            else:
                username_match = re.search(
                    r"t\.me/([A-Za-z0-9_]+)",
                    link,
                    re.IGNORECASE
                )
                if username_match:
                    username = username_match.group(1)
                    await client(JoinChannelRequest(username))
                    logger.info(f"✅ Вступили: @{username}")

        except UserAlreadyParticipantError:
            pass
        except InviteHashExpiredError:
            logger.warn(f"⚠️ Инвайт истёк: {link}")
        except Exception as e:
            logger.error(f"❌ Ошибка вступления {link}: {e}")


async def _click_check_button(message):
    if not hasattr(message, 'reply_markup') or not message.reply_markup:
        return
    try:
        clicked = False
        for row in message.reply_markup.rows:
            for button in row.buttons:
                label = getattr(button, 'text', '') or ''
                data = getattr(button, 'data', b'') or b''
                data_str = data.decode('utf-8', errors='ignore') if isinstance(data, bytes) else str(data)
                if (
                    'check' in label.lower() or
                    'subscri' in label.lower() or
                    'провер' in label.lower() or
                    'активир' in label.lower() or
                    'check' in data_str.lower() or
                    'subscribe' in data_str.lower()
                ):
                    await message.click(data=data)
                    clicked = True
                    break
            if clicked:
                break
        if not clicked:
            await message.click(0)
    except Exception as e:
        logger.error(f"❌ Ошибка нажатия кнопки: {e}")


async def _process(client, chat_id, text):
    matches = list(dict.fromkeys(CHECK_PATTERN.findall(text)))
    if not matches:
        return

    now = time.monotonic()
    expired = [k for k, t in _seen_codes.items() if now - t > SEEN_TTL]
    for k in expired:
        del _seen_codes[k]

    for code in matches:
        if code in _seen_codes:
            continue
        _seen_codes[code] = now
        logger.info(f"🍀 Lovec: найден чек {code} из чата {chat_id}")
        try:
            await client.send_message("CryptoBot", f"/start {code}")
        except Exception as e:
            logger.error(f"❌ Ошибка отправки: {e}")


async def _handle_cryptobot_message(event, client):
    text = event.raw_text or ""

    if "Вы получили" in text:
        msg_id = event.message.id
        if msg_id not in _counted_ids:
            _counted_ids.add(msg_id)
            _handle_received(text)
        return

    if "уже активирован" in text.lower():
        logger.warn("⚠️ Чек уже активирован")
        return

    if "от чека для" in text.lower():
        logger.warn("⚠️ Требуется пароль")
        return

    if "не найден" in text.lower() or "недостаточного баланса" in text.lower():
        logger.warn("⚠️ Чек не найден или удалён")
        return

    if "подпишитесь" in text.lower() or "subscribe" in text.lower():
        all_text = _extract_all_urls(event.message)
        links = _extract_channel_links(all_text)
        if links:
            await _join_channels(client, links)
        await _click_check_button(event.message)


class LovedModule(BaseModule):
    def register(self, client: TelegramClient) -> None:
        super().register(client)

        @client.on(events.NewMessage())
        async def _monitor(event):
            if not _state["active"]:
                return

            chat_id = event.chat_id
            if chat_id in _ignore_ids:
                return

            if event.sender_id and event.sender_id in _ignore_ids:
                return

            if event.out and event.raw_text and event.raw_text.strip().startswith('.'):
                return

            text = _extract_all_urls(event.message)
            await _process(client, chat_id, text)

        @client.on(events.NewMessage(chats='CryptoBot'))
        async def _cryptobot_new(event):
            await _handle_cryptobot_message(event, client)

        @client.on(events.MessageEdited(chats='CryptoBot'))
        async def _cryptobot_edited(event):
            await _handle_cryptobot_message(event, client)


def setup() -> BaseModule:
    _load_ignore()
    _load_stats()
    return LovedModule(
        name="Lovec",
        version="1.1",
        description="🍀 Ловец чеков @CryptoBot (мультивалюта)",
        commands={
            "lovec": _lovec_cmd,
        },
        examples=[
            "`.lovec on` – включить ловец",
            "`.lovec off` – выключить ловец",
            "`.lovec stats` – статистика",
            "`.lovec ignore <id>` – не ловить чеки с этого чата",
            "`.lovec ignore list` – список игнора",
            "`.lovec ignore clear` – очистить игнор-лист",
        ],
    )