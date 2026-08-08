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
