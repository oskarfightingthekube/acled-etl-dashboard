from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parents[2] / "main" / ".env"


class Settings(BaseSettings):
    email: str
    password: str
    access_token: str = ""   # opcjonalnie: gotowy token zamiast logowania hasłem (konta Google SSO)
    environment: str = "dev"
    base_url: str = "https://acleddata.com/"
    page_size: int = 5_000
    request_timeout: int = 60
    s3_events_prefix: str = "events/{date}/page_{page:03d}.csv"
    s3_last_run_timestamp: str = "state/last_run_timestamp.txt"
    s3_deletes_prefix: str = "deletes/{date}/page_{page:03d}.csv"

    @property
    def deleted_data_url(self):
        return f"{self.base_url}api/deleted/read"

    @property
    def auth_url(self):
        return f"{self.base_url}oauth/token"

    @property
    def read_data_url(self):
        return f"{self.base_url}api/acled/read"

    @property
    def s3_bronze_bucket(self):
        return f"mw-acled-bronze-{self.environment}"

    @property
    def s3_silver_bucket(self):
        return f"mw-acled-silver-{self.environment}"

    @property
    def glue_database(self):
        return f"acled_{self.environment}"

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_prefix="ACLED_"
    )
