"""Products for the ODPS tests. CI validates what `sample_product` emits.

  python -m tests.fixtures.odps.sample_product out.odps.yaml [full]
"""

import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from backend.domain.entities.data_product import (
    ContractRef,
    DataProduct,
    InputPort,
    ManagementPort,
    OutputPort,
)
from backend.use_cases.data_product.odps import odps_yaml

PRODUCT_ID = uuid.UUID("7a1c2e3f-4b5d-4e6f-8a9b-0c1d2e3f4a5b")
DOMAIN_ID = uuid.UUID("11111111-0000-0000-0000-000000000001")
CADASTRO = uuid.UUID("22222222-0000-0000-0000-000000000002")
EXPOSICAO = uuid.UUID("22222222-0000-0000-0000-000000000001")
CREATED = datetime(2026, 11, 24, 10, 30, tzinfo=timezone(timedelta(hours=-3)))


def make_product(**overrides) -> DataProduct:
    values = {
        "id": PRODUCT_ID,
        "name": "Risco de Crédito",
        "domain_id": DOMAIN_ID,
        "domain": "Risco",
        "status": "active",
        "output_ports": [OutputPort("exposicao", id=uuid.UUID(int=1))],
        "created_at": CREATED,
        "updated_at": CREATED,
    }
    return DataProduct(**{**values, **overrides})


def full_product() -> DataProduct:
    return make_product(
        description={
            "purpose": "Exposição de crédito por cliente",
            "usage": "Lote diário",
            "limitations": "Sem intradiário",
            "custom_properties": [{"property": "audience", "value": "risk"}],
        },
        version="${PRODUCT_VERSION:-1.0.0}",
        type="consumerAligned",
        tenant="acme",
        tags=["risco", "credito"],
        synonyms=[{"synonym": "credit exposure", "locale": "en", "status": "approved"}],
        context={
            "instructions": "Use only for credit risk",
            "constraints": [{"constraint": "Never join with PII"}],
            "verified_statements": [{"question": "Total exposure?", "answer": "sum(amount)"}],
        },
        team={
            "name": "Risco",
            "members": [
                {"username": "ana", "name": "Ana", "role": "owner", "date_in": "2026-01-01"},
                {"username": "bo", "replaced_by_username": "ana"},
            ],
        },
        support=[{"channel": "#risco", "url": "${SUPPORT_URL}", "tool": "slack", "invitation_url": "https://join"}],
        custom_properties=[
            {"property": "cost_center", "value": {"area_code": 42, "nested_list": [1, 2]}},
            {"property": "pii", "value": False},
        ],
        authoritative_definitions=[{"type": "businessDefinition", "url": "https://wiki/risco"}],
        input_ports=[
            InputPort("cadastro", CADASTRO, "2.1.0", id=uuid.UUID(int=2), tags=("raw",)),
            InputPort(
                "core-bancario",
                id=uuid.UUID(int=3),
                deprecated=True,
                authoritative_definitions=({"type": "implementation", "url": "https://wiki/core"},),
            ),
        ],
        output_ports=[
            OutputPort(
                "exposicao",
                EXPOSICAO,
                "1.0.0",
                type="tables",
                description="Exposição por cliente",
                input_contracts=(ContractRef(CADASTRO, "2.1.0"),),
                tags=("gold",),
                custom_properties=({"property": "sla", "value": "daily"},),
                synonyms=({"synonym": "exposure"},),
                context={"instructions": "Aggregated daily"},
                sbom=({"type": "external", "url": "https://sbom/exposicao"},),
                id=uuid.UUID(int=4),
            ),
            OutputPort("alerta-limite", type="topic", id=uuid.UUID(int=5)),
        ],
        management_ports=[
            ManagementPort("metrics", "observability", url="${METRICS_URL}", id=uuid.UUID(int=6)),
            ManagementPort("alerts", "control", type="topic", channel="risco.alertas", id=uuid.UUID(int=7)),
        ],
        repo_url="https://github.com/acme/dp-risco",
    )


if __name__ == "__main__":
    product = full_product() if sys.argv[2:] == ["full"] else make_product()
    Path(sys.argv[1]).write_text(odps_yaml(product), encoding="utf-8")
