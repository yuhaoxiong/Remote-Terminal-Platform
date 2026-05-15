from cryptography.fernet import Fernet, InvalidToken

from app.config import Settings


class EncryptionService:
    def __init__(self, settings: Settings) -> None:
        self.key = settings.credential_encryption_key
        self.fernet = Fernet(self.key.encode("utf-8")) if self.key else None

    @property
    def enabled(self) -> bool:
        return self.fernet is not None

    def encrypt_optional(self, value: str | None) -> str | None:
        if not value:
            return value
        if self.fernet is None:
            return value
        if self.is_encrypted(value):
            return value
        return self.fernet.encrypt(value.encode("utf-8")).decode("utf-8")

    def decrypt_optional(self, value: str | None) -> str | None:
        if not value:
            return value
        if self.fernet is None:
            return value
        try:
            return self.fernet.decrypt(value.encode("utf-8")).decode("utf-8")
        except InvalidToken:
            return value

    def is_encrypted(self, value: str | None) -> bool:
        if not value or self.fernet is None:
            return False
        try:
            self.fernet.decrypt(value.encode("utf-8"))
        except InvalidToken:
            return False
        return True
