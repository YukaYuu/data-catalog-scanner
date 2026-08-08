import os

import psycopg2
import pytest

from scanner.connectors.postgres import PostgresConnector

TEST_DSN = os.environ.get(
    "TEST_POSTGRES_DSN", "postgresql://catalog:catalog@localhost:5432/catalog_demo"
)


def _postgres_available() -> bool:
    try:
        psycopg2.connect(TEST_DSN, connect_timeout=2).close()
        return True
    except psycopg2.OperationalError:
        return False


pytestmark = pytest.mark.skipif(
    not _postgres_available(), reason="requires a live Postgres at TEST_POSTGRES_DSN"
)


@pytest.fixture
def schema():
    schema_name = "test_scanner_schema"
    conn = psycopg2.connect(TEST_DSN)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(f"DROP SCHEMA IF EXISTS {schema_name} CASCADE")
        cur.execute(f"CREATE SCHEMA {schema_name}")
        cur.execute(
            f"""
            CREATE TABLE {schema_name}.widgets (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL
            )
            """
        )
        cur.execute(f"INSERT INTO {schema_name}.widgets (name) VALUES ('a'), ('b'), ('c')")
    yield schema_name
    with conn.cursor() as cur:
        cur.execute(f"DROP SCHEMA IF EXISTS {schema_name} CASCADE")
    conn.close()


def test_list_tables_reports_columns_and_row_count(schema):
    connector = PostgresConnector(source_name="test_source", dsn=TEST_DSN, schema=schema)
    tables = connector.list_tables()

    assert len(tables) == 1
    table = tables[0]
    assert table.table_name == "widgets"
    assert table.schema_name == schema
    assert table.row_count == 3

    columns_by_name = {c.name: c for c in table.columns}
    assert columns_by_name["id"].is_primary_key is True
    assert columns_by_name["name"].is_nullable is False
    assert columns_by_name["name"].is_primary_key is False
