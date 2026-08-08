import psycopg2

from scanner.models import ColumnMetadata, TableMetadata


class PostgresConnector:
    source_type = "postgresql"

    def __init__(self, source_name: str, dsn: str, schema: str):
        self.source_name = source_name
        self.dsn = dsn
        self.schema = schema

    def list_tables(self) -> list[TableMetadata]:
        conn = psycopg2.connect(self.dsn)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = %s AND table_type = 'BASE TABLE'
                    ORDER BY table_name
                    """,
                    (self.schema,),
                )
                table_names = [row[0] for row in cur.fetchall()]

                return [
                    TableMetadata(
                        source_name=self.source_name,
                        source_type=self.source_type,
                        schema_name=self.schema,
                        table_name=table_name,
                        row_count=self._row_count(cur, table_name),
                        columns=self._list_columns(cur, table_name),
                    )
                    for table_name in table_names
                ]
        finally:
            conn.close()

    def _row_count(self, cur, table_name: str) -> int:
        # table_name always comes from information_schema above, never
        # from untrusted input; Postgres has no parameter placeholder
        # for identifiers, so this is the standard way to do this.
        cur.execute(f'SELECT COUNT(*) FROM "{self.schema}"."{table_name}"')
        return cur.fetchone()[0]

    def _list_columns(self, cur, table_name: str) -> list[ColumnMetadata]:
        cur.execute(
            """
            SELECT
                c.column_name,
                c.data_type,
                c.is_nullable,
                c.ordinal_position,
                EXISTS (
                    SELECT 1
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.key_column_usage kcu
                      ON tc.constraint_name = kcu.constraint_name
                     AND tc.table_schema = kcu.table_schema
                    WHERE tc.constraint_type = 'PRIMARY KEY'
                      AND tc.table_schema = %(schema)s
                      AND tc.table_name = %(table)s
                      AND kcu.column_name = c.column_name
                ) AS is_primary_key
            FROM information_schema.columns c
            WHERE c.table_schema = %(schema)s AND c.table_name = %(table)s
            ORDER BY c.ordinal_position
            """,
            {"schema": self.schema, "table": table_name},
        )
        return [
            ColumnMetadata(
                name=name,
                data_type=data_type,
                is_nullable=(is_nullable == "YES"),
                is_primary_key=is_pk,
                ordinal_position=ordinal,
            )
            for name, data_type, is_nullable, ordinal, is_pk in cur.fetchall()
        ]
