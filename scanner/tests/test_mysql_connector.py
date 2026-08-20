import os

import pymysql
import pytest

from scanner.connectors.mysql import MySQLConnector

# Uses the root user (docker-compose's MYSQL_ROOT_PASSWORD) rather than the
# `catalog` user the seed/scanner services use in compose: creating and
# dropping a whole test database needs a privilege the catalog user isn't
# granted (MySQL's official image only grants it privileges on the one
# MYSQL_DATABASE named at container startup).
TEST_HOST = os.environ.get("TEST_MYSQL_HOST", "localhost")
TEST_PORT = int(os.environ.get("TEST_MYSQL_PORT", "3306"))
TEST_ROOT_PASSWORD = os.environ.get("TEST_MYSQL_ROOT_PASSWORD", "root")
TEST_DATABASE = "test_scanner_db"


def _mysql_available() -> bool:
    try:
        pymysql.connect(
            host=TEST_HOST, port=TEST_PORT, user="root", password=TEST_ROOT_PASSWORD,
            connect_timeout=2,
        ).close()
        return True
    except pymysql.err.OperationalError:
        return False


pytestmark = pytest.mark.skipif(
    not _mysql_available(), reason="requires a live MySQL at TEST_MYSQL_HOST"
)


@pytest.fixture
def database():
    conn = pymysql.connect(host=TEST_HOST, port=TEST_PORT, user="root", password=TEST_ROOT_PASSWORD)
    with conn.cursor() as cur:
        cur.execute(f"DROP DATABASE IF EXISTS {TEST_DATABASE}")
        cur.execute(f"CREATE DATABASE {TEST_DATABASE}")
        cur.execute(
            f"""
            CREATE TABLE {TEST_DATABASE}.widgets (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(255) NOT NULL
            )
            """
        )
        cur.execute(f"INSERT INTO {TEST_DATABASE}.widgets (name) VALUES ('a'), ('b'), ('c')")
    conn.commit()
    yield TEST_DATABASE
    with conn.cursor() as cur:
        cur.execute(f"DROP DATABASE IF EXISTS {TEST_DATABASE}")
    conn.commit()
    conn.close()


def _connector(database: str) -> MySQLConnector:
    return MySQLConnector(
        source_name="test_source", host=TEST_HOST, port=TEST_PORT,
        user="root", password=TEST_ROOT_PASSWORD, database=database,
    )


def test_list_tables_reports_columns_and_row_count(database):
    tables = _connector(database).list_tables()

    assert len(tables) == 1
    table = tables[0]
    assert table.table_name == "widgets"
    assert table.schema_name == database
    assert table.row_count == 3

    columns_by_name = {c.name: c for c in table.columns}
    # MySQL exposes primary-key-ness directly on information_schema.columns
    # (COLUMN_KEY='PRI'), unlike Postgres which needs a constraint join --
    # this is exercising that different code path, not just re-testing the
    # same logic as PostgresConnector.
    assert columns_by_name["id"].is_primary_key is True
    assert columns_by_name["name"].is_nullable is False
    assert columns_by_name["name"].is_primary_key is False

    assert columns_by_name["id"].profile.null_count == 0
    assert columns_by_name["id"].profile.distinct_count == 3
    assert columns_by_name["name"].profile.min_value == "a"
    assert columns_by_name["name"].profile.max_value == "c"


def test_profile_handles_nulls_and_empty_table(database):
    conn = pymysql.connect(host=TEST_HOST, port=TEST_PORT, user="root", password=TEST_ROOT_PASSWORD)
    with conn.cursor() as cur:
        cur.execute(f"ALTER TABLE {database}.widgets ADD COLUMN note VARCHAR(255)")
        cur.execute(f"UPDATE {database}.widgets SET note = 'x' WHERE name = 'a'")
        cur.execute(f"CREATE TABLE {database}.empty_widgets (id INT AUTO_INCREMENT PRIMARY KEY, note VARCHAR(255))")
    conn.commit()
    conn.close()

    tables = {t.table_name: t for t in _connector(database).list_tables()}

    note_profile = {c.name: c for c in tables["widgets"].columns}["note"].profile
    assert note_profile.null_count == 2  # 'b' and 'c' rows have no note
    assert note_profile.distinct_count == 1
    assert note_profile.min_value == "x"
    assert note_profile.max_value == "x"

    # SUM(CASE ...) over zero rows is NULL, not 0 -- same `or 0` fallback
    # as the other two connectors' _profile_columns.
    empty_note_profile = {c.name: c for c in tables["empty_widgets"].columns}["note"].profile
    assert empty_note_profile.null_count == 0
    assert empty_note_profile.distinct_count == 0
    assert empty_note_profile.min_value is None
    assert empty_note_profile.max_value is None
