"""The ODPS sections of the data product API, field by field (ODPS v1.1.0)."""

import pytest
from pydantic import ValidationError

from backend.interface.schemas.common import SupportChannel, TeamMember
from backend.interface.schemas.data_product import (
    Context,
    CustomProperty,
    DataProductWriteModel,
    ManagementPortModel,
    OutputPortModel,
    ProductSupportChannel,
    Team,
)

BASE = {"name": "Risk", "domain_id": "8f7c3c55-0000-0000-0000-000000000001"}


@pytest.mark.parametrize("url", ["${SUPPORT_URL}", "${SUPPORT_URL:-https://chat/risk}", "https://chat/risk"])
def test_support_url_accepts_a_variable(url):
    assert ProductSupportChannel(channel="#risk", url=url).url == url


@pytest.mark.parametrize("url", ["javascript:alert(1)", "javascript:${X}", "ftp://files"])
def test_support_url_refuses_other_schemes(url):
    with pytest.raises(ValidationError, match="http, https or mailto"):
        ProductSupportChannel(channel="#risk", url=url)


def test_contract_support_still_refuses_a_variable():
    with pytest.raises(ValidationError):
        SupportChannel(channel="#risk", url="${SUPPORT_URL}")


def test_product_support_needs_a_url():
    with pytest.raises(ValidationError, match="url"):
        ProductSupportChannel(channel="#risk")


def test_custom_property_needs_a_property_and_a_value():
    with pytest.raises(ValidationError, match="value"):
        CustomProperty(property="k")
    with pytest.raises(ValidationError, match="property"):
        CustomProperty(property=" ", value=1)
    assert CustomProperty(property="k", value={"nested": [1, 2]}).value == {"nested": [1, 2]}


def test_unknown_odps_key_is_refused():
    with pytest.raises(ValidationError, match="colour"):
        Team(members=[{"username": "ana", "colour": "blue"}])


def test_team_member_takes_the_odps_fields():
    member = Team(members=[{"username": "ana", "date_in": "2026-01-01", "tags": ["lead"]}]).members[0]
    assert (member.date_in, member.tags) == ("2026-01-01", ["lead"])


def test_contract_team_member_is_unchanged():
    with pytest.raises(ValidationError):
        TeamMember(username="ana", date_in="2026-01-01")


def test_context_requires_the_question_and_the_constraint():
    with pytest.raises(ValidationError, match="question"):
        Context(verified_statements=[{"answer": "42"}])
    with pytest.raises(ValidationError, match="constraint"):
        Context(constraints=[{}])


def test_management_port_needs_a_name_and_a_content_and_defaults_to_rest():
    assert ManagementPortModel(name="m", content="observability").type == "rest"
    with pytest.raises(ValidationError, match="content"):
        ManagementPortModel(name="m")


def test_only_output_ports_take_synonyms_context_and_sbom():
    output = OutputPortModel(
        name="o", synonyms=[{"synonym": "s"}], context={"instructions": "i"}, sbom=[{"url": "u"}]
    )
    assert (output.synonyms[0].synonym, output.context.instructions) == ("s", "i")
    with pytest.raises(ValidationError, match="synonyms"):
        DataProductWriteModel(**BASE, input_ports=[{"name": "i", "synonyms": [{"synonym": "s"}]}])


def test_description_is_structured_and_defaults_to_empty_texts():
    model = DataProductWriteModel(**BASE)
    assert (model.description.purpose, model.description.usage, model.description.limitations) == ("", "", "")
    with pytest.raises(ValidationError):
        DataProductWriteModel(**BASE, description="plain text")
