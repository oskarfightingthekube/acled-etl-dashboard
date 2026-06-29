from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    email: str
    password: str
    environment: str = "dev"
    base_url: str = "https://acleddata.com/"
    page_size: int = 5_000
    request_timeout: int = 60
    s3_full_load_prefix: str = "events/full_load/page_{page:03d}.csv"
    s3_incremental_prefix: str = "events/incremental/{date}/page_{page:03d}.csv"
    s3_last_run_timestamp: str = "state/last_run_timestamp.txt"

    @property
    def auth_url(self):
        return f"{self.base_url}oauth/token"

    @property
    def read_data_url(self):
        return f"{self.base_url}api/acled/read"

    @property
    def s3_bronze_bucket(self):
        return f"mw-acled-bronze-{self.environment}"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="ACLED_"
    )
