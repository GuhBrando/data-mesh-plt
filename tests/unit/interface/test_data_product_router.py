import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from backend.domain.entities.data_product import (
    EDITABLE_FIELDS,
    ContractRef,
    ContractSummary,
    DataProduct,
    DataProductRuleError,
    InputPort,
    ManagementPort,
    OutputPort,
    PortUsage,
    ProductRef,
)
from backend.domain.entities.user import User
from backend.domain.value_objects.email import Email
from backend.domain.value_objects.user_role import UserRole
from backend.infra.github_client import RepoNameUnavailable
from backend.infra.postgres import get_db_connection
from backend.interface.dependencies import (
    get_create_data_product_use_case,
    get_data_product_repository,
    get_delete_data_product_use_case,
    get_get_data_product_use_case,
    get_github_client,
    get_list_contract_ports_use_case,
    get_list_data_products_use_case,
    get_update_data_product_use_case,
)
from backend.interface.security import get_current_user
from backend.main import app
from backend.use_cases.data_product.save import SavedProduct

NOW = datetime.now(tz=timezone.utc)
PRODUCT_ID = uuid.uuid4()
DOMAIN_ID = uuid.uuid4()
CONTRACT_ID = uuid.uuid4()
PORT_ID = uuid.uuid4()
USER_ID = uuid.uuid4()


def _product(**kw) -> DataProduct:
    fields = {
        "id": PRODUCT_ID,
        "name": "Orders Product",
        "description": {"purpose": "desc", "usage": "", "limitations": ""},
        "domain_id": DOMAIN_ID,
        "domain": "Marketing",
        "status": "active",
        "output_ports": [
            OutputPort(
                "orders",
                CONTRACT_ID,
                "1.0.0",
                type="tables",
                id=PORT_ID,
                contract=ContractSummary("Orders", "active", "1.1.0", "Marketing"),
                consumed_by=(ProductRef(uuid.uuid4(), "Billing", "draft"),),
            )
        ],
        "created_at": NOW,
        "updated_at": NOW,
    }
    return DataProduct(**{**fields, **kw})


def _admin() -> User:
    return User(
        id=USER_ID,
        name="Admin",
        email=Email("admin@example.com"),
        role=UserRole.PLATFORM_ADMIN,
    )


BODY = {
    "name": "Orders Product",
    "description": {"purpose": "desc", "usage": "Daily"},
    "domain_id": str(DOMAIN_ID),
    "status": "active",
    "output_ports": [
        {
            "name": "orders",
            "type": "tables",
            "contract_id": str(CONTRACT_ID),
            "input_contracts": [{"contract_id": str(CONTRACT_ID), "version": "2.0.0"}],
        }
    ],
    "input_ports": [
        {"name": "cad", "contract_id": str(CONTRACT_ID), "version": "2.0.0"},
        {
            "name": "core",
            "authoritative_definitions": [
                {"type": "implementation", "url": "https://wiki/core"}
            ],
        },
    ],
}


@pytest.fixture
def admin_client():
    app.dependency_overrides[get_current_user] = lambda: _admin()
    app.dependency_overrides[get_db_connection] = lambda: AsyncMock()
    app.dependency_overrides[get_github_client] = lambda: None
    yield TestClient(app)
    app.dependency_overrides.clear()


def _use(dependency, **returns) -> AsyncMock:
    mock = AsyncMock()
    for name, value in returns.items():
        setattr(mock, name, value)
    app.dependency_overrides[dependency] = lambda: mock
    return mock


def _github(full_name="acme/dp-marketing-orders-product") -> AsyncMock:
    github = AsyncMock()
    github.create_product_repo.return_value = {
        "html_url": f"https://github.com/{full_name}",
        "full_name": full_name,
    }
    app.dependency_overrides[get_github_client] = lambda: github
    return github


def test_create_maps_the_body_to_ports(admin_client):
    uc = _use(get_create_data_product_use_case)
    uc.execute.return_value = SavedProduct(_product(), [])
    assert admin_client.post("/api/v1/data-products", json=BODY).status_code == 201
    kwargs = uc.execute.await_args.kwargs
    assert (kwargs["name"], kwargs["domain_id"], kwargs["status"]) == (
        "Orders Product",
        DOMAIN_ID,
        "active",
    )
    assert kwargs["output_ports"] == [
        OutputPort(
            "orders",
            CONTRACT_ID,
            None,
            type="tables",
            input_contracts=(ContractRef(CONTRACT_ID, "2.0.0"),),
        )
    ]
    assert kwargs["input_ports"] == [
        InputPort("cad", CONTRACT_ID, "2.0.0"),
        InputPort(
            "core",
            authoritative_definitions=(
                {"type": "implementation", "url": "https://wiki/core"},
            ),
        ),
    ]


def test_create_returns_ports_lineage_and_warnings(admin_client):
    uc = _use(get_create_data_product_use_case)
    uc.execute.return_value = SavedProduct(_product(), ["Contract Orders is deprecated"])
    resp = admin_client.post("/api/v1/data-products", json=BODY)
    body = resp.json()
    assert body["warnings"] == ["Contract Orders is deprecated"]
    assert (body["domain"], body["status"], body["deprecated"]) == (
        "Marketing",
        "active",
        False,
    )
    [port] = body["output_ports"]
    assert port["id"] == str(PORT_ID)
    assert port["contract"] == {
        "title": "Orders",
        "status": "active",
        "version": "1.1.0",
        "domain": "Marketing",
    }
    assert [p["name"] for p in port["consumed_by"]] == ["Billing"]
    assert body["input_ports"] == []
    assert "data_contracts_id" not in body


def test_create_rule_error_is_422_with_one_msg_per_rule(admin_client):
    uc = _use(get_create_data_product_use_case)
    uc.execute.side_effect = DataProductRuleError(["first", "second"])
    resp = admin_client.post("/api/v1/data-products", json=BODY)
    assert resp.status_code == 422
    assert resp.json()["detail"] == [{"msg": "first"}, {"msg": "second"}]


def test_create_without_outputs_reaches_the_aggregate(admin_client):
    uc = _use(get_create_data_product_use_case)
    uc.execute.side_effect = DataProductRuleError(
        ["A data product needs at least one output"]
    )
    body = {k: v for k, v in BODY.items() if k != "output_ports"}
    resp = admin_client.post("/api/v1/data-products", json=body)
    assert resp.status_code == 422
    assert uc.execute.await_args.kwargs["output_ports"] == []


def test_new_products_default_to_draft(admin_client):
    uc = _use(get_create_data_product_use_case)
    uc.execute.return_value = SavedProduct(_product(status="draft"), [])
    body = {k: v for k, v in BODY.items() if k != "status"}
    admin_client.post("/api/v1/data-products", json=body)
    assert uc.execute.await_args.kwargs["status"] == "draft"


def test_a_port_needs_a_name(admin_client):
    _use(get_create_data_product_use_case)
    body = {**BODY, "output_ports": [{"name": ""}]}
    assert admin_client.post("/api/v1/data-products", json=body).status_code == 422


def test_put_is_a_full_replace(admin_client):
    uc = _use(get_update_data_product_use_case)
    uc.execute.return_value = SavedProduct(_product(name="Updated"), [])
    resp = admin_client.put(f"/api/v1/data-products/{PRODUCT_ID}", json=BODY)
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated"
    args, kwargs = uc.execute.await_args
    assert args == (PRODUCT_ID,)
    assert set(kwargs) == set(EDITABLE_FIELDS)


def test_put_rule_error_is_422(admin_client):
    uc = _use(get_update_data_product_use_case)
    uc.execute.side_effect = DataProductRuleError(["nope"])
    resp = admin_client.put(f"/api/v1/data-products/{PRODUCT_ID}", json=BODY)
    assert resp.status_code == 422


def test_put_of_a_missing_product_is_404(admin_client):
    uc = _use(get_update_data_product_use_case)
    uc.execute.return_value = None
    resp = admin_client.put(f"/api/v1/data-products/{uuid.uuid4()}", json=BODY)
    assert resp.status_code == 404


def test_a_partial_put_is_refused(admin_client):
    _use(get_update_data_product_use_case)
    resp = admin_client.put(f"/api/v1/data-products/{PRODUCT_ID}", json={"name": "X"})
    assert resp.status_code == 422


@pytest.mark.parametrize("status, deprecated", [("deprecated", True), ("draft", False)])
def test_deprecated_is_derived_in_the_response(admin_client, status, deprecated):
    uc = _use(get_get_data_product_use_case)
    uc.execute.return_value = _product(status=status)
    resp = admin_client.get(f"/api/v1/data-products/{PRODUCT_ID}")
    assert resp.json()["deprecated"] is deprecated


def test_get_returns_input_lineage(admin_client):
    producer = ProductRef(uuid.uuid4(), "Cadastro PF", "active")
    uc = _use(get_get_data_product_use_case)
    uc.execute.return_value = _product(
        input_ports=[
            InputPort("cad", CONTRACT_ID, "2.0.0", id=uuid.uuid4(), produced_by=(producer,))
        ]
    )
    [port] = admin_client.get(f"/api/v1/data-products/{PRODUCT_ID}").json()["input_ports"]
    assert port["produced_by"] == [
        {"id": str(producer.id), "name": "Cadastro PF", "status": "active"}
    ]
    assert port["contract"] is None


def test_get_data_product_not_found(admin_client):
    uc = _use(get_get_data_product_use_case)
    uc.execute.return_value = None
    assert admin_client.get(f"/api/v1/data-products/{uuid.uuid4()}").status_code == 404


def test_list_data_products(admin_client):
    uc = _use(get_list_data_products_use_case)
    uc.execute.return_value = [_product(), _product(id=uuid.uuid4(), name="B")]
    resp = admin_client.get("/api/v1/data-products")
    assert [p["name"] for p in resp.json()] == ["Orders Product", "B"]
    assert all(p["warnings"] == [] for p in resp.json())


def test_list_data_products_does_not_provision(admin_client):
    uc = _use(get_list_data_products_use_case)
    uc.execute.return_value = [_product()]
    github = _github()
    admin_client.get("/api/v1/data-products")
    github.create_product_repo.assert_not_awaited()


def test_delete_data_product(admin_client):
    _use(get_get_data_product_use_case).execute.return_value = _product()
    _use(get_delete_data_product_use_case).execute.return_value = True
    assert admin_client.delete(f"/api/v1/data-products/{PRODUCT_ID}").status_code == 204


def test_delete_data_product_not_found(admin_client):
    _use(get_get_data_product_use_case).execute.return_value = None
    _use(get_delete_data_product_use_case)
    assert admin_client.delete(f"/api/v1/data-products/{uuid.uuid4()}").status_code == 404


def test_contract_ports_lists_usage(admin_client):
    product_id = uuid.uuid4()
    uc = _use(get_list_contract_ports_use_case)
    uc.execute.return_value = [
        PortUsage(product_id, "Risk", "Risco", "active", "output", "exp", CONTRACT_ID, "1.0.0")
    ]
    resp = admin_client.get(f"/api/v1/data-contracts/{CONTRACT_ID}/ports")
    assert resp.status_code == 200
    assert resp.json() == [
        {
            "product_id": str(product_id),
            "product_name": "Risk",
            "domain": "Risco",
            "status": "active",
            "role": "output",
            "port_name": "exp",
            "version": "1.0.0",
        }
    ]
    uc.execute.assert_awaited_once_with(CONTRACT_ID)


def test_contract_ports_404_for_unknown_contract(admin_client):
    _use(get_list_contract_ports_use_case).execute.return_value = None
    resp = admin_client.get(f"/api/v1/data-contracts/{uuid.uuid4()}/ports")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Data contract not found"


# ── GitHub repository provisioning (warn-only) ───────────────────────────────


def test_repo_name_uses_the_products_domain(admin_client):
    uc = _use(get_create_data_product_use_case)
    uc.execute.return_value = SavedProduct(
        _product(name="Exposição de Crédito", domain="Risco"), []
    )
    product_repo = _use(get_data_product_repository)
    github = _github("acme/dp-risco-exposicao-de-credito")
    resp = admin_client.post("/api/v1/data-products", json=BODY)
    assert resp.status_code == 201
    assert github.create_product_repo.await_args.args[0] == "dp-risco-exposicao-de-credito"
    product_repo.update_repo_url.assert_awaited_once_with(
        PRODUCT_ID, "https://github.com/acme/dp-risco-exposicao-de-credito"
    )
    readme = github.push_scaffold.await_args.args[1]["README.md"]
    assert "**Domain:** Risco" in readme
    assert resp.json()["repo_url"] == "https://github.com/acme/dp-risco-exposicao-de-credito"


def test_create_without_github_leaves_repo_url_empty(admin_client):
    _use(get_create_data_product_use_case).execute.return_value = SavedProduct(
        _product(), []
    )
    resp = admin_client.post("/api/v1/data-products", json=BODY)
    assert resp.json()["repo_url"] is None


def test_create_swallows_github_errors(admin_client):
    _use(get_create_data_product_use_case).execute.return_value = SavedProduct(
        _product(), []
    )
    product_repo = _use(get_data_product_repository)
    _github().create_product_repo.side_effect = RuntimeError("boom")
    resp = admin_client.post("/api/v1/data-products", json=BODY)
    assert resp.status_code == 201
    assert resp.json()["repo_url"] is None
    product_repo.update_repo_url.assert_not_awaited()


def test_create_retries_with_a_suffixed_name_when_the_name_is_taken(admin_client):
    _use(get_create_data_product_use_case).execute.return_value = SavedProduct(
        _product(), []
    )
    _use(get_data_product_repository)
    suffixed = f"dp-marketing-orders-product-{PRODUCT_ID.hex[:8]}"
    github = _github()
    github.create_product_repo.side_effect = [
        RepoNameUnavailable("archived repo holds the name"),
        {"html_url": f"https://github.com/acme/{suffixed}", "full_name": f"acme/{suffixed}"},
    ]
    resp = admin_client.post("/api/v1/data-products", json=BODY)
    attempted = [c.args[0] for c in github.create_product_repo.await_args_list]
    assert attempted == ["dp-marketing-orders-product", suffixed]
    assert resp.json()["repo_url"] == f"https://github.com/acme/{suffixed}"


def test_create_keeps_the_repo_url_when_the_scaffold_fails(admin_client):
    _use(get_create_data_product_use_case).execute.return_value = SavedProduct(
        _product(), []
    )
    product_repo = _use(get_data_product_repository)
    github = _github()
    github.push_scaffold.side_effect = RuntimeError("scaffold boom")
    resp = admin_client.post("/api/v1/data-products", json=BODY)
    url = "https://github.com/acme/dp-marketing-orders-product"
    product_repo.update_repo_url.assert_awaited_once_with(PRODUCT_ID, url)
    assert resp.json()["repo_url"] == url


def test_get_backfills_the_repo_when_missing(admin_client):
    _use(get_get_data_product_use_case).execute.return_value = _product()
    _use(get_data_product_repository)
    github = _github()
    resp = admin_client.get(f"/api/v1/data-products/{PRODUCT_ID}")
    github.create_product_repo.assert_awaited_once()
    assert resp.json()["repo_url"] == "https://github.com/acme/dp-marketing-orders-product"


def test_get_skips_the_backfill_when_the_repo_exists(admin_client):
    _use(get_get_data_product_use_case).execute.return_value = _product(
        repo_url="https://github.com/acme/dp-existing"
    )
    github = _github()
    admin_client.get(f"/api/v1/data-products/{PRODUCT_ID}")
    github.create_product_repo.assert_not_awaited()


def test_update_backfills_the_repo_when_missing(admin_client):
    _use(get_update_data_product_use_case).execute.return_value = SavedProduct(
        _product(), []
    )
    _use(get_data_product_repository)
    github = _github()
    admin_client.put(f"/api/v1/data-products/{PRODUCT_ID}", json=BODY)
    github.create_product_repo.assert_awaited_once()


def test_delete_archives_the_repo(admin_client):
    _use(get_get_data_product_use_case).execute.return_value = _product(
        repo_url="https://github.com/acme/dp-marketing-orders-product"
    )
    _use(get_delete_data_product_use_case).execute.return_value = True
    github = _github()
    assert admin_client.delete(f"/api/v1/data-products/{PRODUCT_ID}").status_code == 204
    github.archive_repo.assert_awaited_once_with("acme/dp-marketing-orders-product")


def test_delete_without_repo_does_not_archive(admin_client):
    _use(get_get_data_product_use_case).execute.return_value = _product()
    _use(get_delete_data_product_use_case).execute.return_value = True
    github = _github()
    admin_client.delete(f"/api/v1/data-products/{PRODUCT_ID}")
    github.archive_repo.assert_not_awaited()


# ── ODPS plan 2: every other ODPS field ──────────────────────────────────────

SECTIONS_BODY = {
    "version": "${VERSION:-1.0.0}",
    "type": "consumerAligned",
    "tenant": "acme",
    "tags": ["risk"],
    "synonyms": [{"synonym": "credit exposure", "status": "approved"}],
    "context": {
        "instructions": "Credit risk only",
        "constraints": [{"constraint": "No PII joins"}],
        "verified_statements": [{"question": "Total exposure?"}],
    },
    "team": {"name": "Risk", "members": [{"username": "ana", "role": "owner", "date_in": "2026-01-01"}]},
    "support": [{"channel": "#risk", "url": "${SUPPORT_URL}", "tool": "slack"}],
    "custom_properties": [{"property": "cost_center", "value": 42}],
    "authoritative_definitions": [{"type": "businessDefinition", "url": "https://wiki"}],
    "management_ports": [{"name": "metrics", "content": "observability", "url": "https://m"}],
}
STORED_SECTIONS = {
    "version": "${VERSION:-1.0.0}",
    "type": "consumerAligned",
    "tenant": "acme",
    "tags": ["risk"],
    "synonyms": [{"synonym": "credit exposure", "status": "approved"}],
    "context": {
        "instructions": "Credit risk only",
        "constraints": [{"constraint": "No PII joins"}],
        "verified_statements": [{"question": "Total exposure?"}],
    },
    "team": {"name": "Risk", "members": [{"username": "ana", "role": "owner", "date_in": "2026-01-01"}]},
    "support": [{"channel": "#risk", "url": "${SUPPORT_URL}", "tool": "slack"}],
    "custom_properties": [{"property": "cost_center", "value": 42}],
    "authoritative_definitions": [{"type": "businessDefinition", "url": "https://wiki"}],
}


def test_create_passes_every_section_compacted_to_the_use_case(admin_client):
    uc = _use(get_create_data_product_use_case)
    uc.execute.return_value = SavedProduct(_product(), [])
    resp = admin_client.post("/api/v1/data-products", json={**BODY, **SECTIONS_BODY})
    assert resp.status_code == 201, resp.text
    kwargs = uc.execute.await_args.kwargs
    assert {k: kwargs[k] for k in STORED_SECTIONS} == STORED_SECTIONS
    assert kwargs["description"] == {"purpose": "desc", "usage": "Daily", "limitations": ""}
    assert kwargs["management_ports"] == [
        ManagementPort("metrics", "observability", url="https://m")
    ]


def test_port_extras_reach_the_use_case(admin_client):
    uc = _use(get_create_data_product_use_case)
    uc.execute.return_value = SavedProduct(_product(), [])
    body = {**BODY, "output_ports": [{
        "name": "o",
        "tags": ["gold"],
        "synonyms": [{"synonym": "exp"}],
        "context": {"instructions": "daily"},
        "sbom": [{"type": "external", "url": "https://sbom"}],
        "custom_properties": [{"property": "sla", "value": "daily"}],
    }], "input_ports": [{"name": "i", "tags": ["raw"]}]}
    admin_client.post("/api/v1/data-products", json=body)
    kwargs = uc.execute.await_args.kwargs
    assert kwargs["output_ports"] == [OutputPort(
        "o",
        tags=("gold",),
        synonyms=({"synonym": "exp"},),
        context={"instructions": "daily"},
        sbom=({"type": "external", "url": "https://sbom"},),
        custom_properties=({"property": "sla", "value": "daily"},),
    )]
    assert kwargs["input_ports"] == [InputPort("i", tags=("raw",))]


def test_an_input_port_with_synonyms_is_422(admin_client):
    _use(get_create_data_product_use_case)
    body = {**BODY, "input_ports": [{"name": "i", "synonyms": [{"synonym": "s"}]}]}
    assert admin_client.post("/api/v1/data-products", json=body).status_code == 422


def test_response_echoes_sections_and_management_ports(admin_client):
    uc = _use(get_get_data_product_use_case)
    metrics = ManagementPort("metrics", "observability", type="topic", id=uuid.uuid4())
    uc.execute.return_value = _product(
        description={"purpose": "p", "usage": "u", "limitations": "l"},
        management_ports=[metrics],
        **STORED_SECTIONS,
    )
    body = admin_client.get(f"/api/v1/data-products/{PRODUCT_ID}").json()
    assert body["description"]["usage"] == "u"
    assert (body["version"], body["tenant"], body["tags"]) == ("${VERSION:-1.0.0}", "acme", ["risk"])
    assert body["team"]["members"][0]["date_in"] == "2026-01-01"
    assert body["support"][0]["url"] == "${SUPPORT_URL}"
    assert body["context"]["constraints"] == [{"constraint": "No PII joins", "id": None, "tags": [], "custom_properties": [], "authoritative_definitions": []}]
    assert body["management_ports"][0]["id"] == str(metrics.id)
    assert body["management_ports"][0]["type"] == "topic"


def test_readme_and_repo_description_use_the_purpose(admin_client):
    uc = _use(get_create_data_product_use_case)
    uc.execute.return_value = SavedProduct(
        _product(description={"purpose": "Credit exposure by client", "usage": "", "limitations": ""}), []
    )
    _use(get_data_product_repository)
    github = _github()
    admin_client.post("/api/v1/data-products", json=BODY)
    assert github.create_product_repo.await_args.args[1] == "Credit exposure by client"
    assert "Credit exposure by client" in github.push_scaffold.await_args.args[1]["README.md"]


# ── ODPS plan 3: export ──────────────────────────────────────────────────────


def test_odps_export_is_yaml_of_to_odps(admin_client):
    import yaml

    from backend.use_cases.data_product.odps import to_odps
    from tests.fixtures.odps.sample_product import full_product

    product = full_product()
    _use(get_get_data_product_use_case).execute.return_value = product
    resp = admin_client.get(f"/api/v1/data-products/{product.id}/odps")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/plain")
    assert yaml.safe_load(resp.text) == to_odps(product)


def test_odps_export_404_for_unknown_product(admin_client):
    _use(get_get_data_product_use_case).execute.return_value = None
    resp = admin_client.get(f"/api/v1/data-products/{uuid.uuid4()}/odps")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Data product not found"


def test_yaml_keeps_accents(admin_client):
    _use(get_get_data_product_use_case).execute.return_value = _product(name="Exposição de Crédito")
    text = admin_client.get(f"/api/v1/data-products/{PRODUCT_ID}/odps").text
    assert "name: Exposição de Crédito" in text


def test_odps_export_does_not_provision_a_repository(admin_client):
    _use(get_get_data_product_use_case).execute.return_value = _product()
    github = _github()
    admin_client.get(f"/api/v1/data-products/{PRODUCT_ID}/odps")
    github.create_product_repo.assert_not_awaited()
