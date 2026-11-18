"""Contracts for the ODCS tests. CI lints what `sample_contract` emits."""

import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from backend.domain.contract_metadata import empty_server
from backend.domain.entities.data_contract import DataContract
from backend.use_cases.data_contract.odcs import to_odcs
from backend.use_cases.data_contract.yaml_builder import assemble_yaml

NOW = datetime(2026, 11, 1, tzinfo=timezone.utc)
SAMPLE_ID = uuid.UUID("3f2a1c9e-8b7d-4e6f-a5c4-1d2e3f4a5b6c")


def make_field(name="id", type="string", description="", nullable=True, primary_key=False,
               classification="", unique=False, physical_type=""):
    return {"name": name, "type": type, "description": description,
            "nullable": nullable, "primary_key": primary_key,
            "classification": classification, "unique": unique,
            "physical_type": physical_type}


def make_rule(dimension="completeness", column="", operator=">=", threshold="99",
              description=""):
    return {"dimension": dimension, "column": column, "operator": operator,
            "threshold": threshold, "description": description}


def make_contract(**overrides) -> DataContract:
    values = {
        "id": SAMPLE_ID, "title": "Orders", "version": "1.0.0", "owner": "alice",
        "domain": "commerce", "tier": 2, "status": "draft",
        "models": {"fields": [], "quality": []},
        "servicelevels": dict.fromkeys(
            ["freshness", "availability", "retention", "latency"], ""
        ),
        "created_at": NOW, "updated_at": NOW,
    }
    return DataContract(**{**values, **overrides})


def sample_contract() -> DataContract:
    return make_contract(
        title="Customer Orders", version="1.2.0", owner="sales-team",
        status="in_review",
        models={
            "fields": [
                make_field("order_id", "string", "Order identifier", False, True),
                make_field("amount", "float", "Order total in BRL"),
                make_field("created_at", "timestamp", nullable=False),
            ],
            "quality": [
                make_rule("freshness", "", "<=", "24h"),
                make_rule("completeness", "order_id", ">=", "99.5",
                          "Every order has an id"),
                make_rule("validity", "currency", "=", "BRL", "Only BRL orders"),
            ],
        },
        servicelevels={"freshness": "24h", "availability": "99.9%",
                       "retention": "one year", "latency": ""},
    )


DATABRICKS = {**empty_server(), "server": "prod", "type": "databricks", "environment": "prod",
              "host": "adb-1.2.azuredatabricks.net", "catalog": "dmplt", "schema_name": "sales"}
POSTGRES = {**empty_server(), "server": "pg", "type": "postgres", "environment": "dev",
            "host": "db.example.com", "port": 5432, "database": "sales", "schema_name": "public"}
AZURE = {**empty_server(), "server": "lake", "type": "azure",
         "location": "abfss://orders@acct.dfs.core.windows.net/orders/*.parquet", "format": "parquet"}
LOCAL = {**empty_server(), "server": "dev", "type": "local", "path": "./orders.csv", "format": "csv"}
SERVERS = [DATABRICKS, POSTGRES, AZURE, LOCAL]
FIELD = make_field("order_id", "string", "", False, True,
                   classification="internal", unique=True, physical_type="VARCHAR(36)")

# One contract with every metadata section. CI lints what it emits.
FULL_CONTRACT = make_contract(
    status="active", owner="commerce-data",
    models={"fields": [FIELD]},
    description={"purpose": "Orders placed", "usage": "Revenue reporting", "limitations": "Since 2020"},
    team_members=[{"username": "alice@example.com", "name": "Alice", "role": "owner"}],
    support=[{"channel": "#commerce", "url": "https://example.com/c", "tool": "slack", "scope": "interactive"}],
    servers=SERVERS,
)


def emit(contract: DataContract) -> dict[str, Any]:
    """`to_odcs` output after a trip through YAML, like a file in the repository."""
    return yaml.safe_load(yaml.dump(to_odcs(contract), sort_keys=False))


if __name__ == "__main__":
    contract = FULL_CONTRACT if sys.argv[2:] == ["full"] else sample_contract()
    Path(sys.argv[1]).write_text(
        assemble_yaml(contract), encoding="utf-8", newline="\n"
    )


# One list for the emit and the parse tests: the stored text, and what
# slaProperties carries for it. A value that rebuilding would change stays text.
SLA_CASES = [
    ("24h", {"value": 24, "unit": "h"}),
    ("99.9%", {"value": 99.9, "unit": "%"}),
    ("30m", {"value": 30, "unit": "min"}),
    ("24", {"value": 24}),
    ("hourly", {"value": "hourly"}),
    ("24 h", {"value": "24 h"}),
    ("1.50h", {"value": "1.50h"}),
    ("007", {"value": "007"}),
    ("5percent", {"value": "5percent"}),
    ("30min", {"value": "30min"}),
    ("24h\n", {"value": "24h\n"}),
    ("\u0663h", {"value": "\u0663h"}),
    ("1" * 20 + "h", {"value": "1" * 20 + "h"}),
]
