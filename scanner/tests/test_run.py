from scanner.models import TableMetadata
from scanner.run import scan_all


class FakeConnector:
    def __init__(self, source_name, tables=None, error=None):
        self.source_name = source_name
        self._tables = tables or []
        self._error = error

    def list_tables(self):
        if self._error:
            raise self._error
        return self._tables


class FakeStore:
    def __init__(self):
        self.written = []

    def write(self, tables):
        self.written.append(tables)


def _table(name):
    return TableMetadata(
        source_name=name, source_type="fake", schema_name=None,
        table_name=name, row_count=0,
    )


def test_all_connectors_succeed():
    store = FakeStore()
    connectors = [
        FakeConnector("a", tables=[_table("a1")]),
        FakeConnector("b", tables=[_table("b1")]),
    ]

    failed = scan_all(connectors, store)

    assert failed == []
    assert len(store.written) == 2


def test_one_connector_failing_does_not_block_the_others():
    store = FakeStore()
    connectors = [
        FakeConnector("broken", error=RuntimeError("connection refused")),
        FakeConnector("healthy", tables=[_table("t1")]),
    ]

    failed = scan_all(connectors, store)

    assert failed == ["broken"]
    # the healthy connector's tables still got written despite the first
    # connector's failure
    assert len(store.written) == 1
    assert store.written[0] == [_table("t1")]


def test_all_connectors_failing_reports_every_source():
    store = FakeStore()
    connectors = [
        FakeConnector("a", error=RuntimeError("boom a")),
        FakeConnector("b", error=RuntimeError("boom b")),
    ]

    failed = scan_all(connectors, store)

    assert failed == ["a", "b"]
    assert store.written == []
