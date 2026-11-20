import contextlib
import json
import uuid
from datetime import datetime, timezone

import pytest

from backend.infra.repositories.data_contract_repository import PostgresDataContractRepository

NOW = datetime.now(tz=timezone.utc)
DOMAIN_ID = uuid.uuid4()
NEW = dict(description={"purpose": "p", "usage": "", "limitations": ""},
           team_members=[{"username": "a", "name": "", "role": ""}],
           support=[{"channel": "c", "url": "", "tool": "", "scope": ""}],
           servers=[{"server": "s", "type": "local", "path": "./a", "format": "csv"}])
ENCODED = tuple(json.dumps(v) for v in NEW.values())
BASE = dict(title="T", version="1.0.0", owner="o", domain_id=DOMAIN_ID, tier=3, status="draft",
            models={"fields": []}, servicelevels={})


class FakeConnection:
    """Records every statement and replays one canned row."""

    def __init__(self, row=None):
        self.row = row
        self.calls = []

    def transaction(self):
        return contextlib.nullcontext()

    async def fetchrow(self, query, *args):
        self.calls.append((query, args))
        return self.row


def _row() -> dict:
    return {"id": uuid.uuid4(), "title": "T", "version": "1.0.0", "owner": "o", "domain": "d", "tier": 3,
            "status": "draft", "models": "{}", "servicelevels": "{}", "domain_id": DOMAIN_ID,
            "created_at": NOW, "updated_at": NOW, **dict(zip(NEW, ENCODED))}


async def test_get_selects_and_decodes_the_new_columns():
    db = FakeConnection(_row())
    contract = await PostgresDataContractRepository(db).get_by_id(uuid.uuid4())
    assert all(f"dc.{c}" in db.calls[0][0] for c in NEW)
    assert {k: getattr(contract, k) for k in NEW} == NEW


async def test_create_binds_the_new_sections():
    db = FakeConnection(_row())
    await PostgresDataContractRepository(db).create(**BASE, **NEW)
    query, args = db.calls[0]
    assert "$12::jsonb" in query and args[8:12] == ENCODED


async def test_update_binds_contract_id_last():
    db = FakeConnection(_row())
    cid = uuid.uuid4()
    await PostgresDataContractRepository(db).update(cid, **BASE, **NEW)
    query, args = db.calls[0]
    assert "WHERE id = $13" in query and args[8:12] == ENCODED and args[12] == cid


@pytest.mark.parametrize("inserted", [True, False])
async def test_upsert_is_one_statement_that_reports_an_insert(inserted):
    db = FakeConnection({"inserted": inserted})
    assert await PostgresDataContractRepository(db).upsert(uuid.uuid4(), **BASE, **NEW) is inserted
    [(query, args)] = db.calls
    assert "ON CONFLICT (id) DO UPDATE" in query and args[9:13] == ENCODED
