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

    assert columns_by_name["id"].profile.null_count == 0
    assert columns_by_name["id"].profile.distinct_count == 3
    assert columns_by_name["name"].profile.min_value == "a"
    assert columns_by_name["name"].profile.max_value == "c"


def test_profile_handles_nulls_and_empty_table(schema):
    conn = psycopg2.connect(TEST_DSN)
    with conn.cursor() as cur:
        cur.execute(f"ALTER TABLE {schema}.widgets ADD COLUMN note TEXT")
        cur.execute(f"UPDATE {schema}.widgets SET note = 'x' WHERE name = 'a'")
        cur.execute(f"CREATE TABLE {schema}.empty_widgets (id SERIAL PRIMARY KEY, note TEXT)")
    conn.commit()
    conn.close()

    connector = PostgresConnector(source_name="test_source", dsn=TEST_DSN, schema=schema)
    tables = {t.table_name: t for t in connector.list_tables()}

    note_profile = {c.name: c for c in tables["widgets"].columns}["note"].profile
    assert note_profile.null_count == 2  # 'b' and 'c' rows have no note
    assert note_profile.distinct_count == 1
    assert note_profile.min_value == "x"
    assert note_profile.max_value == "x"

    # SUM(CASE ...) over zero rows is NULL, not 0 -- this is the case the
    # `or 0` fallback in _profile_columns exists for.
    empty_note_profile = {c.name: c for c in tables["empty_widgets"].columns}["note"].profile
    assert empty_note_profile.null_count == 0
    assert empty_note_profile.distinct_count == 0
    assert empty_note_profile.min_value is None
    assert empty_note_profile.max_value is None
