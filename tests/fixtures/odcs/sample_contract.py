"""Contracts for the ODCS tests. CI lints what `sample_contract` emits."""

import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from backend.domain.entities.data_contract import DataContract
from backend.use_cases.data_contract.odcs import to_odcs
from backend.use_cases.data_contract.yaml_builder import assemble_yaml

NOW = datetime(2026, 11, 1, tzinfo=timezone.utc)
SAMPLE_ID = uuid.UUID("3f2a1c9e-8b7d-4e6f-a5c4-1d2e3f4a5b6c")


def make_field(name="id", type="string", description="", nullable=True, primary_key=False):
    return {"name": name, "type": type, "description": description,
            "nullable": nullable, "primary_key": primary_key}


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


def emit(contract: DataContract) -> dict[str, Any]:
    """`to_odcs` output after a trip through YAML, like a file in the repository."""
    return yaml.safe_load(yaml.dump(to_odcs(contract), sort_keys=False))


if __name__ == "__main__":
    Path(sys.argv[1]).write_text(
        assemble_yaml(sample_contract()), encoding="utf-8", newline="\n"
    )
