from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Barcha maxfiy/sozlanadigan qiymatlar shu yerdan o'qiladi (.env fayldan).
    Hech qachon SECRET_KEY yoki parollarni kodga yozib qo'ymang.
    """

    secret_key: str
    access_token_expire_minutes: int = 1440
    database_url: str = "sqlite:///./matematikapro.db"
    allowed_origins: str = "http://localhost:3000"

    # Turso (bot ishlatayotgan tashqi baza) — o'quvchilar ma'lumotlarini
    # admin panelga va sayt statistikasiga tortib olish uchun
    turso_database_url: str | None = None
    turso_auth_token: str | None = None

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


settings = Settings()