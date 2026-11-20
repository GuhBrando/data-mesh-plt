"""Stored-shape quality rules for the backend tests."""

from typing import Any


def library_rule(**overrides: Any) -> dict[str, Any]:
    rule: dict[str, Any] = {
        "type": "library",
        "dimension": "completeness",
        "column": "email",
        "metric": "nullValues",
        "operator": "mustBe",
        "value": 0,
        "unit": "rows",
        "valid_values": [],
        "description": "",
    }
    return {**rule, **overrides}


def text_rule(**overrides: Any) -> dict[str, Any]:
    rule: dict[str, Any] = {
        "type": "text",
        "dimension": "consistency",
        "column": "",
        "metric": None,
        "operator": None,
        "value": None,
        "unit": None,
        "valid_values": [],
        "description": "Totals reconcile with the ledger.",
    }
    return {**rule, **overrides}


def orders_contract() -> "DataContract":
    """A fresh contract with every kind of rule the platform emits."""
    import uuid
    from datetime import datetime, timezone

    from backend.domain.entities.data_contract import DataContract
    from backend.interface.schemas.data_contract import SchemaField

    def field(name: str, type_: str, **attrs: Any) -> dict[str, Any]:
        return SchemaField(name=name, type=type_, **attrs).model_dump()

    now = datetime(2026, 11, 1, tzinfo=timezone.utc)
    return DataContract(
        id=uuid.UUID("5b0a2f4e-1c3d-4e5f-8a9b-0c1d2e3f4a5b"),
        title="Customer Orders",
        version="1.0.0",
        owner="sales-team",
        domain="commerce",
        tier=2,
        status="active",
        models={
            "fields": [
                field("order_id", "integer", nullable=False, primary_key=True),
                field("customer_id", "string"),
                field("status", "string"),
                field("amount", "float"),
            ],
            "quality": [
                library_rule(
                    metric="rowCount", column="", operator="mustBeGreaterOrEqualTo",
                    value=5, dimension="completeness",
                ),
                library_rule(
                    metric="duplicateValues", column="order_id", dimension="uniqueness"
                ),
                library_rule(
                    column="customer_id", operator="mustBeLessOrEqualTo", value=1,
                    unit="percent",
                ),
                library_rule(
                    metric="invalidValues", column="status", dimension="conformity",
                    valid_values=["open", "paid", "shipped"],
                ),
                library_rule(column="amount"),
                text_rule(),
            ],
        },
        servicelevels={
            "properties": [
                {"property": "freshness", "value": 24, "unit": "h"},
                {"property": "availability", "value": 99.9, "unit": "%"},
                {"property": "retention", "value": 1, "unit": "y"},
                {"property": "latency", "value": 30, "unit": "min"},
            ]
        },
        created_at=now,
        updated_at=now,
    )
