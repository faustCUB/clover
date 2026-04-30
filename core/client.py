import warnings
import logging
from pathlib import Path

warnings.filterwarnings("ignore")
logging.getLogger("telethon").setLevel(logging.CRITICAL)

from telethon import TelegramClient
from core.account import Account
from utils import logger

SESSIONS_DIR = Path(__file__).parent.parent / "sessions"


class CloverClient(TelegramClient):
    def __init__(self, account: Account):
        self.account = account

        super().__init__(
            session=str(SESSIONS_DIR / account.session_name),
            api_id=account.api_id,
            api_hash=account.api_hash,
            catch_up=False,
        )

    async def start_client(self) -> bool:
        try:
            await self.start(
                phone=self.account.phone,
                password=self.account.password or None,
            )
            me = await self.get_me()
            logger.success(
                f"Аккаунт {logger.accent(me.first_name)} ({self.account.phone}) запущен"
            )
            return True
        except Exception as e:
            logger.error(f"Не удалось запустить {self.account.phone}: {e}")
            return False

    async def run_until_disconnected(self) -> None:
        try:
            await super().run_until_disconnected()
        except ConnectionError as e:
            logger.error(
                f"Соединение с Telegram потеряно ({self.account.phone}): {e}"
            )
        except Exception as e:
            logger.error(
                f"Неожиданная ошибка ({self.account.phone}): {e}"
            )

    async def stop_client(self) -> None:
        try:
            await self.disconnect()
            logger.info(f"Аккаунт {self.account.phone} отключён")
        except Exception:
            pass
