"""Common metadata model that every connector normalizes into,
regardless of what engine it actually talked to.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ColumnProfile:
    """Column-level statistics computed by actually scanning the data,
    as opposed to ColumnMetadata's fields, which come from schema
    introspection alone.

    min_value/max_value are stored as their string representation rather
    than a typed value: the common model has to represent every SQL type
    (numeric, text, date, ...) uniformly, the same reasoning that already
    applies to data_type being a plain str rather than a typed enum. Both
    are None when the column has no non-null values to compare (an empty
    table, or a column that happens to be all NULL).
    """

    null_count: int
    distinct_count: int
    min_value: str | None
    max_value: str | None


@dataclass(frozen=True)
class ColumnMetadata:
    name: str
    data_type: str
    is_nullable: bool
    is_primary_key: bool
    ordinal_position: int
    profile: ColumnProfile | None = None


@dataclass(frozen=True)
class TableMetadata:
    source_name: str
    source_type: str
    schema_name: str | None
    table_name: str
    row_count: int | None
    columns: list[ColumnMetadata] = field(default_factory=list)

    @property
    def qualified_name(self) -> str:
        if self.schema_name:
            return f"{self.schema_name}.{self.table_name}"
        return self.table_name
