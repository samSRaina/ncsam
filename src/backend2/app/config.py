from pathlib import Path

from cryptography.fernet import Fernet
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./placement.db"
    field_encryption_key: str = ""
    cookie_secure: bool = False
    cors_origins: list[str] = ["http://localhost:5173"]
    session_idle_minutes: int = 15
    session_absolute_hours: int = 8
    max_failed_logins: int = 5
    lockout_minutes: int = 15
    docs_enabled: bool = True
    export_max_rows: int = 10000
    mfa_encryption_key: str = ""
    enable_hsts: bool = False
    max_import_size_bytes: int = 5 * 1024 * 1024  # 5MB
    max_import_rows: int = 5000

    def fernet_key(self) -> bytes:
        if self.field_encryption_key:
            return self.field_encryption_key.encode()
        # dev fallback: persist a generated key so restarts can still decrypt
        path = Path(".secrets/field.key")
        if not path.exists():
            path.parent.mkdir(exist_ok=True)
            path.write_bytes(Fernet.generate_key())
        return path.read_bytes().strip()


settings = Settings()
