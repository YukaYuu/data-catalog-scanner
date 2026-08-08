import sqlite3

from scanner.models import ColumnMetadata, TableMetadata


class SQLiteConnector:
    source_type = "sqlite"

    def __init__(self, source_name: str, db_path: str):
        self.source_name = source_name
        self.db_path = db_path

    def list_tables(self) -> list[TableMetadata]:
        conn = sqlite3.connect(self.db_path)
        try:
            table_names = [
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master"
                    " WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
                )
            ]
            return [
                TableMetadata(
                    source_name=self.source_name,
                    source_type=self.source_type,
                    schema_name=None,
                    table_name=table_name,
                    row_count=self._row_count(conn, table_name),
                    columns=self._list_columns(conn, table_name),
                )
                for table_name in table_names
            ]
        finally:
            conn.close()

    def _row_count(self, conn: sqlite3.Connection, table_name: str) -> int:
        # table_name always comes from sqlite_master above, never from
        # untrusted input, so string-formatting it here (SQLite has no
        # parameter placeholder for identifiers) is safe.
        return conn.execute(f'SELECT COUNT(*) FROM "{table_name}"').fetchone()[0]

    def _list_columns(self, conn: sqlite3.Connection, table_name: str) -> list[ColumnMetadata]:
        columns = []
        for cid, name, col_type, notnull, _default, pk in conn.execute(
            f'PRAGMA table_info("{table_name}")'
        ):
            columns.append(
                ColumnMetadata(
                    name=name,
                    data_type=col_type or "unknown",
                    is_nullable=not bool(notnull),
                    is_primary_key=bool(pk),
                    ordinal_position=cid + 1,
                )
            )
        return columns
