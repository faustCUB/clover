import re
import json
from pathlib import Path
from dataclasses import dataclass, field
from telethon import TelegramClient, events
from utils import logger

DISABLED_FILE = Path("disabled_modules.json")


def pluralize(n: int, one: str, few: str, many: str) -> str:
    if 11 <= n % 100 <= 19:
        return many
    r = n % 10
    if r == 1:
        return one
    if 2 <= r <= 4:
        return few
    return many


def load_disabled() -> set:
    if DISABLED_FILE.exists():
        try:
            return set(json.loads(DISABLED_FILE.read_text()))
        except Exception:
            return set()
    return set()


def save_disabled(disabled: set) -> None:
    DISABLED_FILE.write_text(json.dumps(list(disabled)))


@dataclass
class BaseModule:
    name: str
    version: str
    description: str
    commands: dict
    examples: list[str] = field(default_factory=list)

    def register(self, client: TelegramClient) -> None:
        for cmd, handler in self.commands.items():

            def make_logged_handler(command, original_handler):
                async def logged_handler(event):
                    chat = event.chat_id
                    logger.info(
                        f"Команда {logger.accent('.' + command)} > чат {logger.accent(str(chat))}"
                    )
                    try:
                        await original_handler(event)
                        logger.success(f"Команда {logger.accent('.' + command)} выполнена")
                    except Exception as e:
                        logger.error(f"Ошибка в команде .{command}: {e}")
                        raise

                return logged_handler

            client.add_event_handler(
                make_logged_handler(cmd, handler),
                events.NewMessage(outgoing=True, pattern=rf"^\.{re.escape(cmd)}(\s|$)"),
            )

        logger.info(
            f"Модуль {logger.accent(self.name)} загружен ({len(self.commands)} команд)"
        )


class HelpSystem:
    def __init__(self, loader):
        self.loader = loader

    def register(self, client: TelegramClient) -> None:
        loader = self.loader

        @client.on(events.NewMessage(outgoing=True, pattern=r"^\.help(\s+\S+)?$"))
        async def help_handler(event):
            args = event.raw_text.strip().split(maxsplit=1)

            if len(args) == 1:
                logger.info(f"Команда {logger.accent('.help')} > список модулей")

                active = {
                    name: mod for name, mod in loader.modules.items()
                    if name not in loader.disabled
                }
                disabled_count = len(loader.disabled)

                lines = ["**🍀 Загруженные модули:**\n"]
                for mod in active.values():
                    cmds = ", ".join(f"`.{c}`" for c in mod.commands)
                    lines.append(f"• **{mod.name}** v{mod.version} — {cmds}")

                m = len(active)
                c = sum(len(mod.commands) for mod in active.values())
                lines.append(
                    f"\n**{m}** {pluralize(m, 'модуль', 'модуля', 'модулей')} · "
                    f"**{c}** {pluralize(c, 'команда', 'команды', 'команд')}"
                )

                if disabled_count:
                    lines.append(
                        f"**{disabled_count}** {pluralize(disabled_count, 'модуль', 'модуля', 'модулей')} отключено — `.help disabled`"
                    )

                lines.append("\nНапиши .**help** <**модуль**> для подробностей")
                lines.append(" ")
                lines.append("Отключить модуль: .**disable** <**модуль**>")
                lines.append("Включить модуль: .**enable** <**модуль**>")

                await event.edit("\n".join(lines))
                logger.success(f"Команда {logger.accent('.help')} выполнена")
                return

            arg = args[1].lower()

            if arg == "disabled":
                logger.info(f"Команда {logger.accent('.help disabled')}")
                if not loader.disabled:
                    await event.edit("✅ Все модули включены")
                    return

                lines = ["**🚫 Отключённые модули:**\n"]
                for name in sorted(loader.disabled):
                    mod = loader.modules.get(name)
                    if mod:
                        lines.append(f"• **{mod.name}** v{mod.version} — {mod.description}")
                    else:
                        lines.append(f"• **{name}**")

                d = len(loader.disabled)
                lines.append(f"\n**{d}** {pluralize(d, 'модуль', 'модуля', 'модулей')} отключено")
                lines.append("\nВключить: .**enable** <**модуль>**")
                await event.edit("\n".join(lines))
                logger.success(f"Команда {logger.accent('.help disabled')} выполнена")
                return

            module_name = arg
            logger.info(
                f"Команда {logger.accent('.help')} > модуль {logger.accent(module_name)}"
            )
            mod = loader.modules.get(module_name)
            if not mod:
                await event.edit(f"❌ Модуль **{module_name}** не найден")
                logger.warn(f"Модуль {logger.accent(module_name)} не найден")
                return

            is_disabled = module_name in loader.disabled
            status = " · 🚫 отключён" if is_disabled else ""

            lines = [
                f"**{mod.name}** · v{mod.version}{status}",
                f"\n{mod.description}\n",
                "**Команды:**",
            ]
            for cmd in mod.commands:
                lines.append(f"• `.{cmd}`")

            if mod.examples:
                lines.append("\n**Примеры:**")
                for ex in mod.examples:
                    lines.append(ex)

            if is_disabled:
                lines.append("\nВключить: `.enable " + module_name + "`")

            await event.edit("\n".join(lines))
            logger.success(f"Команда {logger.accent('.help')} выполнена")

        @client.on(events.NewMessage(outgoing=True, pattern=r"^\.disable(\s+\S+)?$"))
        async def disable_handler(event):
            args = event.raw_text.strip().split(maxsplit=1)
            if len(args) == 1:
                await event.edit("❌ Укажи модуль: `.disable <модуль>`")
                return

            name = args[1].lower()
            if name not in loader.modules:
                await event.edit(f"❌ Модуль **{name}** не найден")
                logger.warn(f"Попытка отключить несуществующий модуль {logger.accent(name)}")
                return

            if name in loader.disabled:
                await event.edit(f"⚠️ Модуль **{name}** уже отключён")
                return

            loader.disabled.add(name)
            save_disabled(loader.disabled)
            logger.warn(f"Модуль {logger.accent(name)} отключён")
            await event.edit(f"🚫 Модуль **{name}** отключён")

        @client.on(events.NewMessage(outgoing=True, pattern=r"^\.enable(\s+\S+)?$"))
        async def enable_handler(event):
            args = event.raw_text.strip().split(maxsplit=1)
            if len(args) == 1:
                await event.edit("❌ Укажи модуль: `.enable <модуль>`")
                return

            name = args[1].lower()
            if name not in loader.modules:
                await event.edit(f"❌ Модуль **{name}** не найден")
                logger.warn(f"Попытка включить несуществующий модуль {logger.accent(name)}")
                return

            if name not in loader.disabled:
                await event.edit(f"✅ Модуль **{name}** уже включён")
                return

            loader.disabled.discard(name)
            save_disabled(loader.disabled)
            logger.info(f"Модуль {logger.accent(name)} включён")
            await event.edit(f"✅ Модуль **{name}** включён")

        @client.on(events.NewMessage(outgoing=True, pattern=r"^\.(\w+)"))
        async def unknown_command_handler(event):
            cmd = event.pattern_match.group(1)

            known = {"help", "disable", "enable"}
            for name, mod in loader.modules.items():
                if name not in loader.disabled:
                    known.update(mod.commands.keys())

            if cmd not in known:
                for name, mod in loader.modules.items():
                    if name in loader.disabled and cmd in mod.commands:
                        logger.warn(f"Команда {logger.accent('.' + cmd)} — модуль отключён")
                        await event.edit(
                            f"🚫 Команда **.{cmd}** недоступна — модуль **{name}** отключён\n"
                            f"Включить: `.enable {name}`"
                        )
                        return

                logger.warn(f"Неизвестная команда {logger.accent('.' + cmd)}")
                await event.edit(f"❌ Команда **.{cmd}** не существует")
