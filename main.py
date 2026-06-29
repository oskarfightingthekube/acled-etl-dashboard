import logging

from src.ingest import full_load, incremental_load, delete_load


def main():
    logging.basicConfig(level=logging.INFO)
    # full_load()
    # incremental_load()
    delete_load(full=True)


if __name__ == "__main__":
    main()
