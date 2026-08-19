import sqlite3

from scanner.models import ColumnMetadata, ColumnProfile, TableMetadata


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
        rows = list(conn.execute(f'PRAGMA table_info("{table_name}")'))
        profiles = self._profile_columns(conn, table_name, [row[1] for row in rows])
        return [
            ColumnMetadata(
                name=name,
                data_type=col_type or "unknown",
                is_nullable=not bool(notnull),
                is_primary_key=bool(pk),
                ordinal_position=cid + 1,
                profile=profiles.get(name),
            )
            for cid, name, col_type, notnull, _default, pk in rows
        ]

    def _profile_columns(self, conn: sqlite3.Connection, table_name: str,
                          column_names: list[str]) -> dict[str, ColumnProfile]:
        """One query per table (not one per column) computing null_count,
        distinct_count, min, and max for every column at once -- see the
        matching method on PostgresConnector for the full rationale
        (avoiding N+1 queries, and why SUM(CASE WHEN ...) is used instead
        of FILTER).

        Unlike Postgres, sqlite3's default cursor doesn't expose column
        names for aliased expressions in a convenient way, so this reads
        the single result row positionally (4 fields per column, in the
        same order as column_names) instead of by name.
        """
        if not column_names:
            return {}
        select_parts = [
            f'SUM(CASE WHEN "{col}" IS NULL THEN 1 ELSE 0 END), '
            f'COUNT(DISTINCT "{col}"), '
            f'CAST(MIN("{col}") AS TEXT), '
            f'CAST(MAX("{col}") AS TEXT)'
            for col in column_names
        ]
        row = conn.execute(f'SELECT {", ".join(select_parts)} FROM "{table_name}"').fetchone()
        profiles = {}
        for i, col in enumerate(column_names):
            null_count, distinct_count, min_value, max_value = row[i * 4:i * 4 + 4]
            profiles[col] = ColumnProfile(
                null_count=null_count or 0,
                distinct_count=distinct_count,
                min_value=min_value,
                max_value=max_value,
            )
        return profiles
