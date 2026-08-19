import psycopg2
import psycopg2.extras

from scanner.models import TableMetadata

CREATE_CATALOG_SCHEMA_SQL = """
CREATE SCHEMA IF NOT EXISTS catalog;

CREATE TABLE IF NOT EXISTS catalog.tables (
    id SERIAL PRIMARY KEY,
    source_name TEXT NOT NULL,
    source_type TEXT NOT NULL,
    schema_name TEXT NOT NULL DEFAULT '',
    table_name TEXT NOT NULL,
    row_count BIGINT,
    scanned_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source_name, schema_name, table_name)
);

CREATE TABLE IF NOT EXISTS catalog.columns (
    id SERIAL PRIMARY KEY,
    table_id INTEGER NOT NULL REFERENCES catalog.tables(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    data_type TEXT NOT NULL,
    is_nullable BOOLEAN NOT NULL,
    is_primary_key BOOLEAN NOT NULL,
    ordinal_position INTEGER NOT NULL
);

-- ADD COLUMN IF NOT EXISTS rather than folding these into the CREATE TABLE
-- above: pgdata is a named Docker volume (see docker-compose.yml), so a
-- catalog.columns table created by an older version of this scanner
-- persists across `docker compose up` and CREATE TABLE IF NOT EXISTS alone
-- would silently skip adding these columns to it.
ALTER TABLE catalog.columns ADD COLUMN IF NOT EXISTS null_count BIGINT;
ALTER TABLE catalog.columns ADD COLUMN IF NOT EXISTS distinct_count BIGINT;
ALTER TABLE catalog.columns ADD COLUMN IF NOT EXISTS min_value TEXT;
ALTER TABLE catalog.columns ADD COLUMN IF NOT EXISTS max_value TEXT;
"""


class CatalogStore:
    """Persists scan results into a Postgres catalog schema. Sources
    without a schema concept (SQLite) are stored with schema_name=''
    rather than NULL -- Postgres treats every NULL as distinct from
    every other NULL for uniqueness purposes, which would silently
    break the ON CONFLICT dedup below for exactly those sources.
    """

    def __init__(self, dsn: str):
        self.dsn = dsn

    def write(self, tables: list[TableMetadata]) -> None:
        conn = psycopg2.connect(self.dsn)
        try:
            with conn.cursor() as cur:
                cur.execute(CREATE_CATALOG_SCHEMA_SQL)
                for table in tables:
                    self._write_table(cur, table)
            conn.commit()
        finally:
            conn.close()

    def _write_table(self, cur, table: TableMetadata) -> None:
        cur.execute(
            """
            INSERT INTO catalog.tables
                (source_name, source_type, schema_name, table_name, row_count, scanned_at)
            VALUES (%s, %s, %s, %s, %s, now())
            ON CONFLICT (source_name, schema_name, table_name)
            DO UPDATE SET row_count = EXCLUDED.row_count, scanned_at = now()
            RETURNING id
            """,
            (
                table.source_name,
                table.source_type,
                table.schema_name or "",
                table.table_name,
                table.row_count,
            ),
        )
        table_id = cur.fetchone()[0]

        cur.execute("DELETE FROM catalog.columns WHERE table_id = %s", (table_id,))
        if table.columns:
            psycopg2.extras.execute_values(
                cur,
                """
                INSERT INTO catalog.columns
                    (table_id, name, data_type, is_nullable, is_primary_key, ordinal_position,
                     null_count, distinct_count, min_value, max_value)
                VALUES %s
                """,
                [
                    (
                        table_id,
                        c.name,
                        c.data_type,
                        c.is_nullable,
                        c.is_primary_key,
                        c.ordinal_position,
                        c.profile.null_count if c.profile else None,
                        c.profile.distinct_count if c.profile else None,
                        c.profile.min_value if c.profile else None,
                        c.profile.max_value if c.profile else None,
                    )
                    for c in table.columns
                ],
            )
