from dataclasses import dataclass


@dataclass
class Account:
    api_id: int
    api_hash: str
    phone: str
    password: str = ""

    @property
    def session_name(self) -> str:
        return self.phone.replace("+", "").replace(" ", "")

    @property
    def label(self) -> str:
        return self.phone
