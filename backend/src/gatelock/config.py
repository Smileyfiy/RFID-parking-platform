from functools import lru_cache
from zoneinfo import ZoneInfo

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GATELOCK_", env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://gatelock:gatelock@127.0.0.1:5433/gatelock?ssl=disable"
    mqtt_host: str = "localhost"
    mqtt_port: int = 1883
    mqtt_topic_prefix: str = "gatelock"

    jwt_secret: str = "dev-only-secret-change-me-in-production-0000"
    jwt_expire_minutes: int = 12 * 60
    # Fernet key for visitor personal data. Empty means a key derived from jwt_secret (dev only).
    pii_key: str = ""

    timezone: str = "Africa/Nairobi"
    cors_origins: list[str] = ["http://localhost:5173"]

    # Event-processing parameters (seconds unless stated).
    debounce_seconds: int = 5
    reservation_timeout_seconds: int = 180
    denied_burst_count: int = 3
    denied_burst_window_seconds: int = 60
    impossible_travel_seconds: int = 120
    temp_tag_return_minutes: int = 10
    visitor_overstay_grace_minutes: int = 30
    visitor_retention_days: int = 30
    maintenance_interval_seconds: int = 15

    # Offline operation: the allow-list snapshot gates cache (objective vii).
    # Tag UIDs in the snapshot are hashed with this salt; gates hold the same salt.
    sync_salt: str = "dev-sync-salt-change-me"
    sync_interval_seconds: int = 5

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)


@lru_cache
def get_settings() -> Settings:
    return Settings()
