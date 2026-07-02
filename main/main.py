import logging

from src.ingest import event_load


def main():
    logging.basicConfig(level=logging.INFO)
    event_load()

if __name__ == "__main__":
    main()
