import re
import os
import asyncio
import json
import shutil
import hashlib
import tarfile
import tempfile
import requests
from pathlib import Path
from dataclasses import dataclass, field
from telethon import TelegramClient, events
from utils import logger

DISABLED_FILE = Path("disabled_modules.json")

REPO_OWNER = "faustCUB"
REPO_NAME = "clover"
BRANCH = "main"
BOT_ROOT = Path(__file__).parent.parent.resolve()

MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
ALIASES_FILE = os.path.join(MODULE_DIR, "aliases", "aliases.json")


def load_aliases() -> dict:
    path = Path(ALIASES_FILE)
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            return {}
    return {}


def save_aliases(aliases: dict) -> None:
    path = Path(ALIASES_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(aliases, ensure_ascii=False, indent=2))


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


def _file_hash(path: Path) -> str:
    h = hashlib.md5()
    h.update(path.read_bytes())
    return h.hexdigest()


def _collect_github_files(extract_root: Path) -> dict[Path, Path]:
    subdirs = [d for d in extract_root.iterdir() if d.is_dir()]
    if not subdirs:
        return {}
    repo_dir = subdirs[0]

    result = {}
    for file in repo_dir.rglob("*"):
        if file.is_file():
            rel = file.relative_to(repo_dir)
            result[rel] = file
    return result


def run_update() -> tuple[bool, list[str], list[str]]:
    url = f"https://github.com/{REPO_OWNER}/{REPO_NAME}/archive/refs/heads/{BRANCH}.tar.gz"
    tmp_dir = Path(tempfile.mkdtemp(prefix="clover_update_"))

    try:
        archive_path = tmp_dir / "update.tar.gz"
        extract_path = tmp_dir / "extracted"
        extract_path.mkdir()

        logger.info("Загружаю архив с GitHub...")
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()

        with open(archive_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        logger.info("Распаковываю архив...")
        with tarfile.open(archive_path) as tar:
            tar.extractall(extract_path)

        github_files = _collect_github_files(extract_path)

        updated = []
        added = []

        for rel_path, github_abs in github_files.items():
            local_path = BOT_ROOT / rel_path
            github_content = github_abs.read_bytes()

            if local_path.exists():
                if _file_hash(local_path) != hashlib.md5(github_content).hexdigest():
                    local_path.write_bytes(github_content)
                    updated.append(str(rel_path))
                    logger.info(f"Обновлён: {rel_path}")
            else:
                local_path.parent.mkdir(parents=True, exist_ok=True)
                local_path.write_bytes(github_content)
                added.append(str(rel_path))
                logger.info(f"Добавлен: {rel_path}")

        return bool(updated or added), updated, added

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        logger.info("Кэш обновления удалён")


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

    def register_aliases(self, client: TelegramClient, aliases: dict) -> None:
        for alias, cmd in aliases.items():
            if cmd not in self.commands:
                continue
            handler = self.commands[cmd]

            def make_logged_handler(command, alias_name, original_handler):
                async def logged_handler(event):
                    chat = event.chat_id
                    logger.info(
                        f"Алиас {logger.accent('.' + alias_name)} > {logger.accent('.' + command)} > чат {logger.accent(str(chat))}"
                    )
                    try:
                        await original_handler(event)
                        logger.success(f"Алиас {logger.accent('.' + alias_name)} выполнен")
                    except Exception as e:
                        logger.error(f"Ошибка в алиасе .{alias_name}: {e}")
                        raise

                return logged_handler

            client.add_event_handler(
                make_logged_handler(cmd, alias, handler),
                events.NewMessage(outgoing=True, pattern=rf"^\.{re.escape(alias)}(\s|$)"),
            )
            logger.info(f"Алиас {logger.accent('.' + alias)} > {logger.accent('.' + cmd)}")


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

                aliases = load_aliases()
                if aliases:
                    lines.append(f"\n**🔗 Алиасы:** {len(aliases)} — `.help aliases`")

                lines.append("\n**⚙️ Системные команды:**")
                lines.append("• `.help` — список модулей и команд")
                lines.append("• `.help <модуль>` — подробности о модуле")
                lines.append("• `.help disabled` — отключённые модули")
                lines.append("• `.help aliases` — список алиасов")
                lines.append("• `.disable <модуль>` — отключить модуль")
                lines.append("• `.enable <модуль>` — включить модуль")
                lines.append("• `.update` — проверить и установить обновления")
                lines.append("• `.alias <алиас> <команда>` — создать алиас")
                lines.append("• `.unalias <алиас>` — удалить алиас")

                await event.edit("\n".join(lines))
                logger.success(f"Команда {logger.accent('.help')} выполнена")
                return

            arg = args[1].lower()

            if arg == "aliases":
                logger.info(f"Команда {logger.accent('.help aliases')}")
                aliases = load_aliases()
                if not aliases:
                    await event.edit("📭 Алиасов нет — создай: `.alias <алиас> <команда>`")
                    return

                lines = ["**🔗 Алиасы:**\n"]
                for alias, cmd in sorted(aliases.items()):
                    lines.append(f"• `.{alias}` > `.{cmd}`")
                lines.append("\nУдалить: `.unalias <алиас>`")
                await event.edit("\n".join(lines))
                logger.success(f"Команда {logger.accent('.help aliases')} выполнена")
                return

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

            aliases = load_aliases()
            mod_aliases = [a for a, c in aliases.items() if c in mod.commands]
            if mod_aliases:
                lines.append("\n**Алиасы:**")
                for a in mod_aliases:
                    lines.append(f"• `.{a}` > `.{aliases[a]}`")

            if mod.examples:
                lines.append("\n**Примеры:**")
                for ex in mod.examples:
                    lines.append(ex)

            if is_disabled:
                lines.append("\nВключить: `.enable " + module_name + "`")

            await event.edit("\n".join(lines))
            logger.success(f"Команда {logger.accent('.help')} выполнена")

        @client.on(events.NewMessage(outgoing=True, pattern=r"^\.alias(\s.*)?$"))
        async def alias_handler(event):
            args = event.raw_text.strip().split(maxsplit=2)
            if len(args) < 3:
                await event.edit("❌ Использование: `.alias <алиас> <команда>`")
                return

            alias = args[1].lower()
            cmd = args[2].lower()

            if " " in cmd:
                await event.edit(f"⚠️ Алиасы не поддерживают многословные команды типа `.{cmd}`")
                return

            all_commands = set()
            for name, mod in loader.modules.items():
                if name not in loader.disabled:
                    all_commands.update(mod.commands.keys())

            if cmd not in all_commands:
                await event.edit(f"❌ Команда `.{cmd}` не найдена")
                return

            if alias in all_commands:
                await event.edit(f"❌ `.{alias}` уже существует как команда модуля")
                return

            aliases = load_aliases()
            aliases[alias] = cmd
            save_aliases(aliases)

            logger.info(f"Алиас {logger.accent('.' + alias)} > {logger.accent('.' + cmd)} создан")
            await event.edit(f"🔗 Алиас `.{alias}` > `.{cmd}` создан\n♻️ Перезапустите программу для применения")

        @client.on(events.NewMessage(outgoing=True, pattern=r"^\.unalias(\s+\S+)?$"))
        async def unalias_handler(event):
            args = event.raw_text.strip().split(maxsplit=1)
            if len(args) < 2:
                await event.edit("❌ Использование: `.unalias <алиас>`")
                return

            alias = args[1].lower()
            aliases = load_aliases()

            if alias not in aliases:
                await event.edit(f"❌ Алиас `.{alias}` не найден")
                return

            del aliases[alias]
            save_aliases(aliases)

            logger.info(f"Алиас {logger.accent('.' + alias)} удалён")
            await event.edit(f"🗑 Алиас `.{alias}` удалён\n♻️ Перезапустите программу для применения")

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

        @client.on(events.NewMessage(outgoing=True, pattern=r"^\.update$"))
        async def update_handler(event):
            logger.info(f"Команда {logger.accent('.update')} запущена")
            await event.edit("🔄 Проверяю обновления...")

            try:
                has_changes, updated, added = await asyncio.get_event_loop().run_in_executor(
                    None, run_update
                )

                if not has_changes:
                    logger.success("Обновлений не найдено")
                    await event.edit("✅ Обновлений не найдено — версия актуальна")
                    return

                lines = ["✅ **Обновление установлено!**\n"]

                if updated:
                    lines.append(f"📝 **Обновлено файлов:** {len(updated)}")
                    for f in updated:
                        lines.append(f"  • `{f}`")

                if added:
                    lines.append(f"\n➕ **Добавлено файлов:** {len(added)}")
                    for f in added:
                        lines.append(f"  • `{f}`")

                lines.append("\n♻️ Перезапустите программу в Termux для применения изменений")

                logger.success(
                    f"Обновление завершено: {len(updated)} обновлено, {len(added)} добавлено"
                )
                await event.edit("\n".join(lines))

            except requests.exceptions.ConnectionError:
                logger.error("Нет подключения к GitHub")
                await event.edit("❌ Нет подключения к интернету")
            except requests.exceptions.HTTPError as e:
                logger.error(f"Ошибка GitHub: {e}")
                await event.edit(f"❌ Ошибка при загрузке с GitHub: `{e}`")
            except Exception as e:
                logger.error(f"Ошибка обновления: {e}")
                await event.edit(f"❌ Ошибка обновления: `{e}`")

        @client.on(events.NewMessage(outgoing=True, pattern=r"^\.(\w+)"))
        async def unknown_command_handler(event):
            cmd = event.pattern_match.group(1)

            aliases = load_aliases()
            known = {"help", "disable", "enable", "update", "alias", "unalias"}
            known.update(aliases.keys())
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
