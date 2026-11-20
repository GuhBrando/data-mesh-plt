import uuid
from datetime import datetime, timezone

from backend.domain.entities.data_contract import DataContract


def test_data_contract_has_required_fields():
    now = datetime.now(tz=timezone.utc)
    contract = DataContract(
        id=uuid.uuid4(),
        title="Orders Contract",
        version="1.0.0",
        owner="data-team",
        domain="commerce",
        tier=2,
        status="draft",
        models={"fields": []},
        servicelevels={"freshness": "24h", "availability": "99.9%", "retention": "365d", "latency": "1h"},
        created_at=now,
        updated_at=now,
    )
    assert contract.title == "Orders Contract"
    assert contract.tier == 2
    assert contract.status == "draft"
    assert contract.models == {"fields": []}


def test_metadata_defaults_are_empty_and_not_shared():
    now = datetime.now(tz=timezone.utc)
    build = lambda: DataContract(
        id=uuid.uuid4(), title="x", version="1.0.0", owner="o", domain="d", tier=4, status="draft",
        models={}, servicelevels={}, created_at=now, updated_at=now,
    )
    first, second = build(), build()
    assert first.description == {"purpose": "", "usage": "", "limitations": ""}
    assert (first.team_members, first.support, first.servers) == ([], [], [])
    first.team_members.append({"username": "a"})
    assert second.team_members == []
