import importlib
from pathlib import Path
from modules.base import BaseModule, HelpSystem, pluralize, load_disabled, load_aliases
from utils import logger


class ModuleLoader:
    def __init__(self):
        self.modules: dict[str, BaseModule] = {}
        self.disabled: set = load_disabled()

    def load_all(self, client) -> None:
        modules_dir = Path("modules")

        for file in sorted(modules_dir.glob("*.py")):
            if file.name.startswith("_") or file.name in ("base.py", "loader.py"):
                continue
            self._load_file(file.stem, client)

        aliases = load_aliases()
        if aliases:
            all_commands: dict[str, BaseModule] = {}
            for mod in self.modules.values():
                for cmd in mod.commands:
                    all_commands[cmd] = mod

            for alias, cmd in aliases.items():
                if cmd in all_commands:
                    all_commands[cmd].register_aliases(client, {alias: cmd})
                else:
                    logger.warn(f"Алиас {logger.accent('.' + alias)} > команда {logger.accent('.' + cmd)} не найдена, пропускаю")

        HelpSystem(self).register(client)

        active = [name for name in self.modules if name not in self.disabled]
        disabled = [name for name in self.modules if name in self.disabled]

        m = len(active)
        c = sum(len(self.modules[name].commands) for name in active)
        logger.success(
            f"Загружено {logger.accent(str(m))} {pluralize(m, 'модуль', 'модуля', 'модулей')}, "
            f"{logger.accent(str(c))} {pluralize(c, 'команда', 'команды', 'команд')}"
        )

        if aliases:
            logger.info(f"Алиасов загружено: {logger.accent(str(len(aliases)))}")

        if disabled:
            d = len(disabled)
            names = ", ".join(disabled)
            logger.warn(
                f"Отключено {logger.accent(str(d))} {pluralize(d, 'модуль', 'модуля', 'модулей')}: {names}"
            )

    def _load_file(self, name: str, client) -> None:
        try:
            module = importlib.import_module(f"modules.{name}")
            instance: BaseModule = module.setup()
            instance.register(client)
            self.modules[instance.name.lower()] = instance

            if hasattr(instance, 'register_listener'):
                instance.register_listener(client)

        except Exception as e:
            logger.error(f"Ошибка загрузки модуля {name}: {e}")

    def stats(self) -> dict:
        return {
            "total": len(self.modules),
            "active": len([n for n in self.modules if n not in self.disabled]),
            "disabled": len(self.disabled),
            "names": list(self.modules.keys()),
        }
