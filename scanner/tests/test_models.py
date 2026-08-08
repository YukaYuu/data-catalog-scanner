from scanner.models import TableMetadata


def test_qualified_name_with_schema():
    table = TableMetadata(
        source_name="s",
        source_type="postgresql",
        schema_name="public",
        table_name="users",
        row_count=0,
    )
    assert table.qualified_name == "public.users"


def test_qualified_name_without_schema():
    table = TableMetadata(
        source_name="s",
        source_type="sqlite",
        schema_name=None,
        table_name="widgets",
        row_count=0,
    )
    assert table.qualified_name == "widgets"
