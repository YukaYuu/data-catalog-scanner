import os
import sqlite3
import tempfile

from scanner.connectors.sqlite import SQLiteConnector


def test_list_tables_reports_columns_and_row_count():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.sqlite")
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE widgets (id INTEGER PRIMARY KEY, name TEXT NOT NULL)")
        conn.execute("INSERT INTO widgets (id, name) VALUES (1, 'a'), (2, 'b')")
        conn.commit()
        conn.close()

        connector = SQLiteConnector(source_name="test_source", db_path=db_path)
        tables = connector.list_tables()

        assert len(tables) == 1
        table = tables[0]
        assert table.table_name == "widgets"
        assert table.source_type == "sqlite"
        assert table.schema_name is None
        assert table.row_count == 2

        columns_by_name = {c.name: c for c in table.columns}
        assert columns_by_name["id"].is_primary_key is True
        assert columns_by_name["name"].is_nullable is False
        assert columns_by_name["name"].ordinal_position == 2

        assert columns_by_name["id"].profile.null_count == 0
        assert columns_by_name["id"].profile.distinct_count == 2
        assert columns_by_name["id"].profile.min_value == "1"
        assert columns_by_name["id"].profile.max_value == "2"
        assert columns_by_name["name"].profile.min_value == "a"
        assert columns_by_name["name"].profile.max_value == "b"


def test_profile_handles_nulls_and_empty_table():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.sqlite")
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE widgets (id INTEGER PRIMARY KEY, note TEXT)")
        conn.execute("CREATE TABLE empty_widgets (id INTEGER PRIMARY KEY, note TEXT)")
        conn.execute("INSERT INTO widgets (id, note) VALUES (1, 'a'), (2, NULL), (3, NULL)")
        conn.commit()
        conn.close()

        connector = SQLiteConnector(source_name="test_source", db_path=db_path)
        tables = {t.table_name: t for t in connector.list_tables()}

        note_profile = {c.name: c for c in tables["widgets"].columns}["note"].profile
        assert note_profile.null_count == 2
        assert note_profile.distinct_count == 1  # COUNT(DISTINCT) ignores NULLs
        assert note_profile.min_value == "a"
        assert note_profile.max_value == "a"

        # SUM(CASE ...) over zero rows is NULL, not 0 -- this is the case
        # the `or 0` fallback in _profile_columns exists for.
        empty_note_profile = {c.name: c for c in tables["empty_widgets"].columns}["note"].profile
        assert empty_note_profile.null_count == 0
        assert empty_note_profile.distinct_count == 0
        assert empty_note_profile.min_value is None
        assert empty_note_profile.max_value is None


def test_ignores_sqlite_internal_tables():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.sqlite")
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE widgets (id INTEGER PRIMARY KEY)")
        conn.execute("CREATE UNIQUE INDEX idx_widgets_id ON widgets (id)")
        conn.commit()
        conn.close()

        connector = SQLiteConnector(source_name="test_source", db_path=db_path)
        table_names = {t.table_name for t in connector.list_tables()}

        assert table_names == {"widgets"}
