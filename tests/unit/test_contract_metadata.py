import pytest

from backend.domain.contract_metadata import empty_server, server_problems

VALID = {
    "databricks": {"server": "prod", "type": "databricks", "catalog": "dmplt", "schema_name": "sales"},
    "postgres": {"server": "pg", "type": "postgres", "host": "db.example.com", "port": 5432,
                 "database": "sales", "schema_name": "public"},
    "azure": {"server": "lake", "type": "azure", "format": "parquet",
              "location": "abfss://orders@acct.dfs.core.windows.net/orders/*.parquet"},
    "local": {"server": "dev", "type": "local", "path": "./orders.csv", "format": "csv"},
}


def _server(kind: str, **overrides) -> dict:
    return {**empty_server(), **VALID[kind], **overrides}


@pytest.mark.parametrize("server", [*(_server(k) for k in VALID),
                                    _server("databricks", host="adb-1.2.azuredatabricks.net")])
def test_valid_server_has_no_problems(server):
    assert server_problems(server) == []


@pytest.mark.parametrize("kind, key", [
    ("databricks", "catalog"), ("databricks", "schema_name"),
    ("postgres", "host"), ("postgres", "port"), ("postgres", "database"), ("postgres", "schema_name"),
    ("azure", "location"), ("azure", "format"), ("local", "path"), ("local", "format"),
])
def test_missing_required_key_is_named(kind, key):
    assert any(key in p for p in server_problems(_server(kind, **{key: empty_server()[key]})))


@pytest.mark.parametrize("kind, key, value", [
    ("databricks", "port", 443), ("postgres", "catalog", "c"), ("azure", "host", "h.example.com"),
    ("azure", "schema_name", "s"), ("local", "schema_name", "s"), ("local", "location", "az://x/y"),
])
def test_key_the_type_does_not_take_is_named(kind, key, value):
    assert any(key in p for p in server_problems(_server(kind, **{key: value})))


@pytest.mark.parametrize("server", [
    {**empty_server(), "server": "x", "type": "s3"},
    _server("local", server=""),
    *(_server("postgres", host=h) for h in (
        "user:pw@db.example.com", "https://db.example.com", "db.example.com/path", "db.example.com?token=x")),
    *(_server("azure", location=loc) for loc in (
        "https://acct.blob.core.windows.net/c/p?sv=1&sig=abc", "abfss://u:pw@acct.dfs.core.windows.net/p",
        "just a path")),
    *(_server("postgres", port=p) for p in (0, 65536, "5432", "${DB_PORT}")),
])
def test_invalid_server_has_a_problem(server):
    assert server_problems(server)


def test_problem_text_never_contains_the_value():
    problems = server_problems(_server("postgres", host="user:not-a-real-secret@db"))
    assert "not-a-real-secret" not in " ".join(problems)
