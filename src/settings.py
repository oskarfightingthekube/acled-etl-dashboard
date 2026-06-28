from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    email: str
    password: str
    environment: str = "dev"
    base_url: str = "https://acleddata.com/"
    auth_url: str = f"{base_url}oauth/token"
    page_size: int = 5_000
    request_timeout: int = 60

    @property
    def s3_bronze_bucket(self):
        return f"mw-acled-bronze-{self.environment}"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="ACLED_"
    )
