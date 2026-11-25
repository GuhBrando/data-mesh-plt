import uuid
from datetime import datetime, timezone

import pytest

from backend.domain.entities.data_product import (
    EDITABLE_FIELDS,
    PRODUCT_SECTIONS,
    PRODUCT_STATUSES,
    ContractRef,
    DataProduct,
    DataProductRuleError,
    InputPort,
    ManagementPort,
    OutputPort,
    ProductRef,
    empty_product_description,
)
from backend.domain.naming import slugify

DOMAIN = uuid.uuid4()
C1, C2 = uuid.uuid4(), uuid.uuid4()
NOW = datetime.now(tz=timezone.utc)
OUT = OutputPort(name="exposure")


def _product(**kw) -> DataProduct:
    fields = {"name": "Risk", "domain_id": DOMAIN, "output_ports": [OUT]}
    return DataProduct(**{**fields, **kw})


def _broken(**kw) -> list[str]:
    with pytest.raises(DataProductRuleError) as e:
        _product(**kw)
    return e.value.messages


def test_port_name_from_title():
    assert slugify("Exposição de Crédito") == "exposicao-de-credito"
    assert slugify("  Orders / EU  ") == "orders-eu"
    assert slugify("???") == ""


def test_the_five_odps_statuses():
    assert PRODUCT_STATUSES == ("proposed", "draft", "active", "deprecated", "retired")


def test_a_product_needs_an_output():
    assert _broken(output_ports=[]) == ["A data product needs at least one output"]


def test_status_must_be_an_odps_value():
    assert _broken(status="live") == [
        "Status must be one of: proposed, draft, active, deprecated, retired"
    ]


def test_new_products_are_drafts():
    assert _product().status == "draft"


@pytest.mark.parametrize(
    "status, deprecated",
    [
        ("proposed", False),
        ("draft", False),
        ("active", False),
        ("deprecated", True),
        ("retired", True),
    ],
)
def test_deprecated_follows_status(status, deprecated):
    assert _product(status=status).deprecated is deprecated


def test_ports_are_kept_as_tuples():
    product = _product(input_ports=[InputPort(name="core")])
    assert product.input_ports == (InputPort(name="core"),)
    assert product.output_ports == (OUT,)


def test_input_contracts_must_cite_own_inputs():
    output = OutputPort(name="exposure", input_contracts=(ContractRef(C2, "1.0.0"),))
    messages = _broken(
        input_ports=[InputPort(name="cad", contract_id=C1, version="1.0.0")],
        output_ports=[output],
    )
    assert messages == [
        f"Output exposure is built from version 1.0.0 of contract {C2},"
        " which is not one of this product's inputs"
    ]


def test_input_contracts_must_match_the_inputs_version():
    output = OutputPort(name="exposure", input_contracts=(ContractRef(C1, "2.0.0"),))
    assert len(
        _broken(
            input_ports=[InputPort(name="cad", contract_id=C1, version="1.0.0")],
            output_ports=[output],
        )
    ) == 1


def test_input_contracts_may_cite_an_own_input():
    output = OutputPort(name="exposure", input_contracts=(ContractRef(C1, "1.0.0"),))
    product = _product(
        input_ports=[InputPort(name="cad", contract_id=C1, version="1.0.0")],
        output_ports=[output],
    )
    assert product.output_ports[0].input_contracts == (ContractRef(C1, "1.0.0"),)


def test_an_external_input_cannot_be_cited():
    output = OutputPort(name="exposure", input_contracts=(ContractRef(C1, "1.0.0"),))
    assert len(
        _broken(input_ports=[InputPort(name="core", version="1.0.0")], output_ports=[output])
    ) == 1


def test_all_broken_rules_are_reported_together():
    assert _broken(status="live", output_ports=[]) == [
        "Status must be one of: proposed, draft, active, deprecated, retired",
        "A data product needs at least one output",
    ]


def test_revised_keeps_identity_and_read_fields():
    product = DataProduct(
        id=uuid.uuid4(),
        name="Risk",
        description={"purpose": "d"},
        domain_id=DOMAIN,
        domain="Risco",
        status="active",
        output_ports=[OUT],
        repo_url="https://github.com/acme/dp-risco-risk",
        created_at=NOW,
        updated_at=NOW,
    )
    other_domain = uuid.uuid4()
    revised = product.revised(
        name="Risk 2",
        description={"purpose": "d2"},
        domain_id=other_domain,
        status="deprecated",
        input_ports=[],
        output_ports=[OutputPort(name="v2")],
    )
    assert (revised.id, revised.domain, revised.repo_url) == (
        product.id,
        "Risco",
        product.repo_url,
    )
    assert (revised.created_at, revised.updated_at) == (NOW, NOW)
    assert (revised.name, revised.description, revised.domain_id) == (
        "Risk 2",
        {"purpose": "d2"},
        other_domain,
    )
    assert revised.status == "deprecated"
    assert revised.output_ports == (OutputPort(name="v2"),)


def test_revised_checks_the_rules_again():
    with pytest.raises(DataProductRuleError):
        _product().revised(
            name="Risk",
            description={"purpose": "d"},
            domain_id=DOMAIN,
            status="draft",
            input_ports=[],
            output_ports=[],
        )


def test_a_retired_product_cannot_leave_retired():
    with pytest.raises(DataProductRuleError) as e:
        _product(status="retired").revised(
            name="Risk",
            description={"purpose": "d"},
            domain_id=DOMAIN,
            status="active",
            input_ports=[],
            output_ports=[OUT],
        )
    assert e.value.messages == ["A retired data product cannot change status"]


def test_a_retired_product_can_still_be_edited():
    revised = _product(status="retired").revised(
        name="New name",
        description={"purpose": "d"},
        domain_id=DOMAIN,
        status="retired",
        input_ports=[],
        output_ports=[OUT],
    )
    assert revised.name == "New name"


def test_a_product_can_be_retired():
    revised = _product(status="active").revised(
        name="Risk",
        description={"purpose": "d"},
        domain_id=DOMAIN,
        status="retired",
        input_ports=[],
        output_ports=[OUT],
    )
    assert revised.status == "retired"


def test_ports_compare_without_read_fields():
    seen = InputPort("cad", C1, "1.0.0", produced_by=(ProductRef(C2, "x", "active"),))
    assert seen == InputPort("cad", C1, "1.0.0")


def test_rule_error_reads_as_its_messages():
    error = DataProductRuleError(["a", "b"])
    assert str(error) == "a; b"
    assert error.messages == ["a", "b"]


SECTIONS = {
    "version": "1.2.0",
    "type": "consumerAligned",
    "tenant": "${TENANT}",
    "tags": ["risk"],
    "synonyms": [{"synonym": "credit exposure"}],
    "context": {"instructions": "Use for credit risk only"},
    "team": {"name": "Risk", "members": [{"username": "ana"}]},
    "support": [{"channel": "#risk", "url": "https://chat/risk"}],
    "custom_properties": [{"property": "cost_center", "value": 42}],
    "authoritative_definitions": [{"type": "businessDefinition", "url": "https://wiki"}],
}


def test_sections_default_to_empty():
    product = _product()
    assert (product.version, product.type, product.tenant) == (None, None, None)
    for section in ("tags", "synonyms", "support", "custom_properties", "authoritative_definitions"):
        assert getattr(product, section) == []
    assert (product.context, product.team) == ({}, {})
    assert product.management_ports == ()
    assert product.description == empty_product_description()


def test_description_defaults_to_the_three_texts():
    assert empty_product_description() == {"purpose": "", "usage": "", "limitations": ""}


def test_the_sections_are_the_odps_ones():
    assert PRODUCT_SECTIONS == tuple(SECTIONS)
    assert set(EDITABLE_FIELDS) == {
        "name", "description", "domain_id", "status", *SECTIONS,
        "input_ports", "output_ports", "management_ports",
    }


def test_sections_are_stored_as_given():
    product = _product(**SECTIONS)
    assert {s: getattr(product, s) for s in SECTIONS} == SECTIONS


def test_management_ports_are_kept_as_a_tuple():
    port = ManagementPort("metrics", "observability", url="https://metrics")
    assert _product(management_ports=[port]).management_ports == (port,)
    assert port.type == "rest"


def test_revised_carries_every_editable_field():
    port = ManagementPort("metrics", "observability")
    values = {
        "name": "New",
        "description": {"purpose": "p", "usage": "u", "limitations": "l"},
        "domain_id": uuid.uuid4(),
        "status": "active",
        **SECTIONS,
        "input_ports": [InputPort("in", tags=("a",))],
        "output_ports": [OutputPort("out", sbom=({"url": "https://sbom"},))],
        "management_ports": [port],
    }
    revised = _product(id=uuid.uuid4()).revised(**values)
    for field in EDITABLE_FIELDS:
        expected = values[field]
        if field.endswith("_ports"):
            expected = tuple(expected)
        assert getattr(revised, field) == expected, field


def test_revised_keeps_what_it_is_not_given():
    product = _product(**SECTIONS)
    assert product.revised(name="Other").tags == ["risk"]


def test_revised_refuses_an_unknown_field():
    with pytest.raises(TypeError, match="colour"):
        _product().revised(colour="red")


def test_output_port_extras_compare_by_value():
    a = OutputPort("o", context={"instructions": "x"}, synonyms=({"synonym": "s"},))
    assert a == OutputPort("o", context={"instructions": "x"}, synonyms=({"synonym": "s"},))
    assert a != OutputPort("o")
