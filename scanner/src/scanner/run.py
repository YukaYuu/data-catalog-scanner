import os

from scanner.catalog_store import CatalogStore
from scanner.connectors.postgres import PostgresConnector
from scanner.connectors.sqlite import SQLiteConnector


def main() -> None:
    catalog_dsn = os.environ["CATALOG_DSN"]
    source_postgres_dsn = os.environ["SOURCE_POSTGRES_DSN"]
    source_sqlite_path = os.environ["SOURCE_SQLITE_PATH"]

    connectors = [
        PostgresConnector(
            source_name="chiyoda_bunkyo_realestate",
            dsn=source_postgres_dsn,
            schema="source_realestate",
        ),
        SQLiteConnector(
            source_name="tokyo_anaba_spots",
            db_path=source_sqlite_path,
        ),
    ]

    store = CatalogStore(catalog_dsn)
    for connector in connectors:
        tables = connector.list_tables()
        store.write(tables)
        print(f"[{connector.source_name}] scanned {len(tables)} tables")


if __name__ == "__main__":
    main()
