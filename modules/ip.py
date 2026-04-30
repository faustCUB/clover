import requests
from modules.base import BaseModule
from utils import logger


async def _ip_lookup(event):
    args = event.raw_text.strip().split(maxsplit=1)
    ip = args[1] if len(args) > 1 else None

    if not ip and event.is_reply:
        try:
            reply = await event.get_reply_message()
            ip = reply.message.strip()
        except Exception:
            pass

    if not ip:
        await event.edit("❌ Укажи IP-адрес или ответь на сообщение, содержащее IP")
        logger.error("IP-адрес не указан")
        return

    await event.edit("🍀 Запрашиваю информацию по IP...")

    try:
        fields = "66846719"
        url = f"http://ip-api.com/json/{ip}?fields={fields}&lang=ru"

        r = requests.get(url, timeout=10)
        data = r.json()

        if data.get("status") != "success":
            error = data.get("message", "Неизвестная ошибка")
            await event.edit(f"❌ Не удалось получить данные:\n{error}")
            logger.warn(f"Ошибка API для {logger.accent(ip)}: {error}")
            return

        text = f"""**🔍 Информация по IP: `{data.get('query')}`**

**📍 Основная информация**
Страна: **{data.get('country')}** ({data.get('countryCode')})
Регион: **{data.get('regionName')}** ({data.get('region')})
Город: **{data.get('city')}**
Район: **{data.get('district') or '—'}**
Почтовый индекс: `{data.get('zip') or '—'}`

**🌐 Геолокация**
Широта: `{data.get('lat')}`
Долгота: `{data.get('lon')}`
Часовой пояс: `{data.get('timezone')}`
UTC смещение: `{data.get('offset')}`

**🏢 Провайдер**
ISP: **{data.get('isp') or '—'}**
Организация: **{data.get('org') or '—'}**
AS: `{data.get('as') or '—'}`
AS Name: `{data.get('asname') or '—'}`

**🛡️ Безопасность**
Прокси: **{'Да' if data.get('proxy') else 'Нет'}**
Хостинг: **{'Да' if data.get('hosting') else 'Нет'}**
Мобильный: **{'Да' if data.get('mobile') else 'Нет'}**

**🔗 Полезные ссылки**
• [Whois](https://whois.net/ip/{ip})
• [VirusTotal](https://www.virustotal.com/gui/ip-address/{ip})
• [AbuseIPDB](https://www.abuseipdb.com/check/{ip})
• [Shodan](https://www.shodan.io/host/{ip})
"""

        await event.edit(text, link_preview=False)
        logger.success(f"Данные по IP {logger.accent(ip)} получены")

    except requests.exceptions.Timeout:
        await event.edit("❌ Таймаут запроса к API")
        logger.error(f"Таймаут запроса для {ip}")
    except Exception as e:
        await event.edit(f"❌ Ошибка: {str(e)}")
        logger.error(f"Ошибка при поиске IP {ip}: {e}")


def setup() -> BaseModule:
    return BaseModule(
        name="Ip",
        version="1.0.0",
        description="Информация по IP-адресу",
        commands={
            "ip": _ip_lookup,
        },
        examples=["`.ip 1.1.1.1` – пробить айпи", "`.ip` (реплаем) – пробить айпи"],
    )
