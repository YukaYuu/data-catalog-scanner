from typing import Protocol

from scanner.models import TableMetadata


class Connector(Protocol):
    """Something that can introspect a data source and report its
    tables/columns in the common TableMetadata shape. Each engine gets
    its own implementation because the actual introspection mechanism
    (information_schema queries vs. PRAGMA statements, for example)
    differs completely between them.
    """

    source_name: str
    source_type: str

    def list_tables(self) -> list[TableMetadata]: ...
