from dataclasses import dataclass

import requests
import logging

from src.settings import Settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Token:
    access_token: str
    refresh_token: str


class ACLEDClient:

    def __init__(self):
        self.settings = Settings()
        self._session = requests.Session()
        self.get_token()

    def get_token(self):
        response = self._session.post(
            self.settings.auth_url,
            data={
                "username": self.settings.email,
                "password": self.settings.password,
                "grant_type": "password",
                "client_id": "acled",
                "scope": "authenticated",
            }
        )
        response.raise_for_status()
        data = response.json()
        self._token = Token(
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
        )
        logger.info(f"auth successful{self._token.access_token[:10]}")

    def get_pages(self):
        url = self.settings.read_data_url
        headers = {"Authorization": f"Bearer {self._token.access_token}"}
        page = 1

        while True:
            response = self._session.get(url, params={"_format": "csv",
                                                      "page": page}, headers=headers)
            response.raise_for_status()
            data = response.text
            row_count = data.strip().count("\n")

            yield data
            logger.info(f"page {page}, rows {row_count}")

            if row_count < self.settings.page_size:
                break
            page += 1
