import os
import sys

from scanner.catalog_store import CatalogStore
from scanner.connectors.mysql import MySQLConnector
from scanner.connectors.postgres import PostgresConnector
from scanner.connectors.sqlite import SQLiteConnector


def scan_all(connectors, store) -> list[str]:
    """Scans every connector, writing each one's tables to the catalog as it
    succeeds. Returns the list of source_names that failed.

    Each connector is independent: one source failing (e.g. unreachable DB, a
    schema it can't introspect) shouldn't stop the others from being scanned.
    Whatever succeeded before the failure stays committed (CatalogStore.write
    commits per connector), so a failed source just keeps its last-known-good
    catalog entry instead of the whole run aborting.
    """
    failed_sources = []
    for connector in connectors:
        try:
            tables = connector.list_tables()
            store.write(tables)
            print(f"[{connector.source_name}] scanned {len(tables)} tables")
        except Exception as exc:
            failed_sources.append(connector.source_name)
            print(f"[{connector.source_name}] FAILED: {exc}", file=sys.stderr)
    return failed_sources


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
        MySQLConnector(
            source_name="dblp_coauthorship",
            host=os.environ["SOURCE_MYSQL_HOST"],
            port=int(os.environ.get("SOURCE_MYSQL_PORT", "3306")),
            user=os.environ["SOURCE_MYSQL_USER"],
            password=os.environ["SOURCE_MYSQL_PASSWORD"],
            database=os.environ["SOURCE_MYSQL_DATABASE"],
        ),
    ]

    store = CatalogStore(catalog_dsn)
    failed_sources = scan_all(connectors, store)

    if failed_sources:
        print(f"scan finished with {len(failed_sources)} failed source(s): {', '.join(failed_sources)}",
              file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
