import logging

from src.client import ACLEDClient


def main():
    logging.basicConfig(level=logging.INFO)
    client = ACLEDClient()
    client.get_token()


if __name__ == "__main__":
    main()
