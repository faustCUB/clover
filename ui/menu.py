import os
import asyncio
from rich.console import Console
from rich.text import Text
from rich.prompt import Prompt

from core.account import Account
from core.manager import AccountManager
from modules.loader import ModuleLoader
from utils import logger

console = Console()


BANNER = """ ██████╗██╗      ██████╗ ██╗   ██╗███████╗██████╗ 
██╔════╝██║     ██╔═══██╗██║   ██║██╔════╝██╔══██╗
██║     ██║     ██║   ██║██║   ██║█████╗  ██████╔╝
██║     ██║     ██║   ██║╚██╗ ██╔╝██╔══╝  ██╔══██╗
╚██████╗███████╗╚██████╔╝ ╚████╔╝ ███████╗██║  ██║
 ╚═════╝╚══════╝ ╚═════╝   ╚═══╝  ╚══════╝╚═╝  ╚═╝"""


def clear() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def print_banner() -> None:
    console.print(Text(BANNER, style="bold #00ff00"), justify="left")
    console.print("[#00ff00]userbot   [#3a6b50]тгк: [#00ff88]@cloverUB[/]")
    console.print()


def print_menu(accounts: list[Account]) -> None:
    print_banner()

    idx = 1
    account_indices = {}

    if accounts:
        console.print("[#7ec8a0]  Аккаунты:[/]")
        for acc in accounts:
            console.print(f"  [bold #00ff88]{idx}.[/] {acc.phone}")
            account_indices[idx] = acc
            idx += 1
        console.print()

    console.print("[#7ec8a0]  Меню:[/]")
    add_idx = idx;       console.print(f"  [bold #00ff88]{add_idx}.[/] Добавить аккаунт"); idx += 1

    del_idx = None
    if accounts:
        del_idx = idx;   console.print(f"  [bold #00ff88]{del_idx}.[/] Удалить аккаунт"); idx += 1

    exit_idx = idx;      console.print(f"  [bold #00ff88]{exit_idx}.[/] Выход")
    console.print()

    return account_indices, add_idx, del_idx, exit_idx


async def run_account(manager: AccountManager, account: Account) -> None:
    clear()
    print_banner()

    client = manager.get_client(account)
    manager.current_client = client
    loader = ModuleLoader()

    ok = await client.start_client()
    if not ok:
        await asyncio.sleep(2)
        return

    loader.load_all(client)

    stats = loader.stats()
    console.print(
        f"  [#7ec8a0]Модули:[/] [bold #00ff88]{stats['total']}[/]  "
        + "  ".join(f"[#3a6b50]{n}[/]" for n in stats["names"])
    )
    console.print(
        "\n  [#3a6b50]Нажми[/] [bold #00ff88]CTRL+C[/] [#3a6b50]для возврата в меню[/]\n"
    )

    import signal as _signal

    loop = asyncio.get_running_loop()
    task = loop.create_task(client.run_until_disconnected())

    def _cancel(*_):
        task.cancel()

    def _noop(*_):
        pass

    try:
        loop.add_signal_handler(_signal.SIGINT, _cancel)
    except (NotImplementedError, OSError):
        pass

    try:
        await task
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    except Exception as e:
        logger.error(f"Ошибка при работе аккаунта: {e}")
        await asyncio.sleep(2)
    finally:
        try:
            loop.add_signal_handler(_signal.SIGINT, _noop)
        except (NotImplementedError, OSError):
            pass
        await manager.stop_current()


async def menu_loop() -> None:
    manager = AccountManager()
    manager.load()

    while True:
        clear()
        account_indices, add_idx, del_idx, exit_idx = print_menu(manager.accounts)

        try:
            raw = Prompt.ask("[bold #00ff88]>[/]").strip()
        except (KeyboardInterrupt, EOFError):
            continue

        if not raw.isdigit():
            continue

        choice = int(raw)

        if choice in account_indices:
            await run_account(manager, account_indices[choice])
            continue

        if choice == add_idx:
            clear()
            print_banner()
            console.print("[#7ec8a0]  Новый аккаунт[/]\n")
            try:
                api_id   = int(Prompt.ask("[#7ec8a0]  api_id  [/]").strip())
                api_hash = Prompt.ask("[#7ec8a0]  api_hash[/]").strip()
                phone    = Prompt.ask("[#7ec8a0]  номер телефона[/]").strip()
                password = Prompt.ask(
                    "[#7ec8a0]  2FA пароль[/] [#3a6b50](Enter — пропустить)[/]",
                    default=""
                ).strip()
                acc = Account(api_id=api_id, api_hash=api_hash, phone=phone, password=password)
                manager.save_account(acc)
                await asyncio.sleep(1)
            except (ValueError, KeyboardInterrupt):
                logger.warn("Отменено")
                await asyncio.sleep(1)
            continue

        if del_idx and choice == del_idx:
            clear()
            print_banner()
            console.print("[#7ec8a0]  Удалить аккаунт:[/]\n")
            for i, acc in enumerate(manager.accounts, 1):
                console.print(f"  [bold #00ff88]{i}.[/] {acc.phone}")
            console.print()
            try:
                num = Prompt.ask("[bold #00ff88]>[/]").strip()
                if num.isdigit():
                    i = int(num) - 1
                    if 0 <= i < len(manager.accounts):
                        phone = manager.accounts[i].phone
                        manager.remove_account(phone)
                        logger.success(f"Аккаунт {phone} удалён")
                        await asyncio.sleep(1)
            except KeyboardInterrupt:
                pass
            continue

        if choice == exit_idx:
            clear()
            break