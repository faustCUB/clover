import json
from pathlib import Path

from core.account import Account
from core.client import CloverClient
from utils import logger

BASE_DIR = Path(__file__).parent.parent
SESSIONS_DIR = BASE_DIR / "sessions"


class AccountManager:
    CONFIG_PATH = SESSIONS_DIR / "config.json"

    def __init__(self):
        self.accounts: list[Account] = []
        self.current_client: CloverClient | None = None
        SESSIONS_DIR.mkdir(exist_ok=True)

    def load(self) -> None:
        if not self.CONFIG_PATH.exists():
            self._save([])
            return

        data = json.loads(self.CONFIG_PATH.read_text(encoding="utf-8"))
        self.accounts = [
            Account(
                api_id=a["api_id"],
                api_hash=a["api_hash"],
                phone=a["phone"],
                password=a.get("password", ""),
            )
            for a in data.get("accounts", [])
        ]

    def save_account(self, account: Account) -> None:
        self.load()
        if any(a.phone == account.phone for a in self.accounts):
            logger.warn(f"Аккаунт {account.phone} уже существует")
            return
        self.accounts.append(account)
        self._save([self._to_dict(a) for a in self.accounts])
        logger.success(f"Аккаунт {account.phone} сохранён")

    def remove_account(self, phone: str) -> bool:
        self.accounts = [a for a in self.accounts if a.phone != phone]
        self._save([self._to_dict(a) for a in self.accounts])
        return True

    def get_client(self, account: Account) -> CloverClient:
        return CloverClient(account)

    def session_path(self, account: Account) -> Path:
        return SESSIONS_DIR / account.session_name

    async def stop_current(self) -> None:
        if self.current_client:
            await self.current_client.stop_client()
            self.current_client = None

    def _to_dict(self, a: Account) -> dict:
        return {
            "api_id": a.api_id,
            "api_hash": a.api_hash,
            "phone": a.phone,
            "password": a.password,
        }

    def _save(self, accounts: list) -> None:
        self.CONFIG_PATH.write_text(
            json.dumps({"accounts": accounts}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
