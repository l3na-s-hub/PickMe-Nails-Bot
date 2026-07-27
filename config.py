from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
import pytz
from datetime import datetime


class Settings(BaseSettings):
    """Настройки приложения, считываемые из переменных окружения / .env файла."""

    bot_token: str = Field(validation_alias="BOT_TOKEN")
    admin_ids_raw: str = Field(validation_alias="ADMIN_IDS")
    db_url: str = Field(
        default="sqlite+aiosqlite:///nail_bot.db",
        validation_alias="DB_URL",
    )

    # Фото для приветственного сообщения и для списка услуг.
    welcome_photo_url: str = Field(default="", validation_alias="WELCOME_PHOTO_URL")
    services_photo_url: str = Field(default="", validation_alias="SERVICES_PHOTO_URL")
    about_photo_url: str = Field(default="", validation_alias="ABOUT_PHOTO_URL")
    
    # Часовой пояс для напоминаний (по умолчанию Москва)
    timezone: str = Field(default="Asia/Yekaterinburg", validation_alias="TIMEZONE")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def admin_ids(self) -> list[int]:
        """Список Telegram ID администраторов."""
        return [int(item.strip()) for item in self.admin_ids_raw.split(",") if item.strip()]
    
    @property
    def tz(self):
        """Получить объект часового пояса."""
        return pytz.timezone(self.timezone)
    
    def now(self) -> datetime:
        """Текущее время в заданном часовом поясе."""
        return datetime.now(self.tz)


config = Settings()