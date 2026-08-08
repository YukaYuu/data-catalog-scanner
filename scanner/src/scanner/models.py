"""Common metadata model that every connector normalizes into,
regardless of what engine it actually talked to.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ColumnMetadata:
    name: str
    data_type: str
    is_nullable: bool
    is_primary_key: bool
    ordinal_position: int


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
