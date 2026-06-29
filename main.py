import logging

from src.ingest import delete_load, event_load


def main():
    logging.basicConfig(level=logging.INFO)
    delete_load(full=True)
    # event_load()


if __name__ == "__main__":
    main()
