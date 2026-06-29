import logging

from src.ingest import full_load


def main():
    logging.basicConfig(level=logging.INFO)
    full_load()


if __name__ == "__main__":
    main()
