import sys
import time
import threading
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))

os.system("cls" if os.name == "nt" else "clear")

_ASCII_ART = r"""
                   ▒██░    ▒▓▓▒                   
                 ▒██████ ▒██████▒                 
               ▒████████░▓████████▓               
              ▓█████████▓██████████░              
              ▒██████████████████▓░               
                ░▒▒▓▓█████████▓▓▒░                
               ▓███████████████████░              
              ▓█████████████████████              
              ░████████▒▓▓▓███████▓░              
                ▒██████ ▓█ ▓█████▒                
                 ░▒▓▓▒░  █▒ ░▓▓▒░                 
                          ▓▒                      
"""

BRIGHT_GREEN = "\033[92m"
RESET        = "\033[0m"

print(f"{BRIGHT_GREEN}{_ASCII_ART}{RESET}")

_SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
_spinner_stop = threading.Event()

def _spin(label: str) -> None:
    i = 0
    while not _spinner_stop.is_set():
        frame = _SPINNER_FRAMES[i % len(_SPINNER_FRAMES)]
        sys.stdout.write(f"\r\033[32m{frame}\033[0m \033[38;5;108m{label}\033[0m   ")
        sys.stdout.flush()
        time.sleep(0.08)
        i += 1

def _start_spinner(label: str) -> threading.Thread:
    _spinner_stop.clear()
    t = threading.Thread(target=_spin, args=(label,), daemon=True)
    t.start()
    return t

def _stop_spinner(t: threading.Thread) -> None:
    _spinner_stop.set()
    t.join()
    sys.stdout.write("\r\033[2K")
    sys.stdout.flush()

def _step(label: str, fn) -> None:
    t = _start_spinner(label)
    fn()
    _stop_spinner(t)

_step("Загрузка системы...", lambda: None)

import warnings, logging
warnings.filterwarnings("ignore")
logging.disable(logging.CRITICAL)

_step("Загрузка asyncio...",  lambda: __import__("asyncio"))
_step("Загрузка telethon...", lambda: __import__("telethon"))
_step("Загрузка rich...",     lambda: __import__("rich"))
_step("Загрузка модулей...",  lambda: __import__("ui.menu"))

import asyncio
from pathlib import Path
from utils.cleaner import Cleaner
from ui.menu import menu_loop

async def main():
    cleaner = Cleaner()
    cleaner.register()
    await menu_loop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass