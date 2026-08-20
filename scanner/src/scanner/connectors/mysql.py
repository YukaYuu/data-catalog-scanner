import pymysql

from scanner.models import ColumnMetadata, ColumnProfile, TableMetadata


class MySQLConnector:
    """Third connector, added to check that the Connector Protocol
    (base.py) actually generalizes past two engines rather than having
    accidentally been designed around Postgres/SQLite's specific
    quirks. Real differences from PostgresConnector, worth naming:

    - **Identifier quoting**: MySQL quotes identifiers with backticks
      (`` `col` ``) by default, not double quotes -- ANSI_QUOTES mode
      would make double quotes work too, but that's a session setting
      this connector shouldn't have to assume is on.
    - **Primary key detection**: MySQL's information_schema.columns has a
      COLUMN_KEY field ('PRI' for primary key) directly on the column
      row. Postgres needs a separate join across
      table_constraints/key_column_usage for the same information (see
      PostgresConnector._list_columns) -- MySQL exposes it more directly.
    - **Casting to text for min/max**: CAST(col AS CHAR), not
      MIN(col)::text (Postgres) or CAST(col AS TEXT) (SQLite).
    - **NULL counting**: the same SUM(CASE WHEN col IS NULL THEN 1 ELSE 0
      END) expression as the other two connectors works unchanged --
      MySQL doesn't support the SQL FILTER clause, so this vindicates the
      earlier choice (see PostgresConnector._profile_columns) to use
      SUM(CASE ...) instead of FILTER for the sake of a shared expression
      across all three engines, not just Postgres/SQLite.

    Uses PyMySQL (pure Python) rather than mysqlclient, to avoid needing
    the MySQL C client library at build time -- the scanner has no
    performance-critical path that would justify the C extension.
    """

    source_type = "mysql"

    def __init__(self, source_name: str, host: str, port: int, user: str, password: str, database: str):
        self.source_name = source_name
        self.connect_kwargs = dict(
            host=host, port=port, user=user, password=password, database=database
        )
        self.schema = database

    def list_tables(self) -> list[TableMetadata]:
        conn = pymysql.connect(**self.connect_kwargs)
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
        # from untrusted input; MySQL has no parameter placeholder for
        # identifiers, so this is the standard way to do this (same
        # reasoning as the other two connectors).
        cur.execute(f"SELECT COUNT(*) FROM `{self.schema}`.`{table_name}`")
        return cur.fetchone()[0]

    def _list_columns(self, cur, table_name: str) -> list[ColumnMetadata]:
        cur.execute(
            """
            SELECT column_name, data_type, is_nullable, ordinal_position, column_key
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            ORDER BY ordinal_position
            """,
            (self.schema, table_name),
        )
        rows = cur.fetchall()
        profiles = self._profile_columns(cur, table_name, [row[0] for row in rows])
        return [
            ColumnMetadata(
                name=name,
                data_type=data_type,
                is_nullable=(is_nullable == "YES"),
                is_primary_key=(column_key == "PRI"),
                ordinal_position=ordinal,
                profile=profiles.get(name),
            )
            for name, data_type, is_nullable, ordinal, column_key in rows
        ]

    def _profile_columns(self, cur, table_name: str, column_names: list[str]) -> dict[str, ColumnProfile]:
        """One query per table, not one per column -- same rationale as
        PostgresConnector._profile_columns. See that method's docstring
        for why SUM(CASE ...) is used for null_count instead of FILTER.
        """
        if not column_names:
            return {}
        select_parts = [
            f"SUM(CASE WHEN `{col}` IS NULL THEN 1 ELSE 0 END) AS `{col}__nulls`, "
            f"COUNT(DISTINCT `{col}`) AS `{col}__distinct`, "
            f"CAST(MIN(`{col}`) AS CHAR) AS `{col}__min`, "
            f"CAST(MAX(`{col}`) AS CHAR) AS `{col}__max`"
            for col in column_names
        ]
        cur.execute(f"SELECT {', '.join(select_parts)} FROM `{self.schema}`.`{table_name}`")
        row = cur.fetchone()
        colnames = [desc[0] for desc in cur.description]
        values = dict(zip(colnames, row))
        return {
            col: ColumnProfile(
                null_count=values[f"{col}__nulls"] or 0,
                distinct_count=values[f"{col}__distinct"],
                min_value=values[f"{col}__min"],
                max_value=values[f"{col}__max"],
            )
            for col in column_names
        }
