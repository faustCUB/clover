import atexit
import signal
import shutil
import os
from pathlib import Path
from utils import logger


class Cleaner:
    def __init__(self, root: str = "."):
        self.root = Path(root)

    def register(self) -> None:
        atexit.register(self.clean)
        signal.signal(signal.SIGTERM, lambda *_: self.clean())

    def clean(self) -> None:
        removed = 0

        for pattern in ["**/__pycache__", "**/*.pyc", "**/*.pyo"]:
            for path in self.root.glob(pattern):
                try:
                    if path.is_dir():
                        shutil.rmtree(path)
                    else:
                        path.unlink()
                    removed += 1
                except Exception:
                    pass

        if removed:
            logger.info(f"Cleaner: удалено {removed} кеш-объектов")
