import copy

import pytest

from backend.domain.contract_evolution import (
    ChangeKind,
    ContractEvolutionError,
    classify_change,
    evolution_violation,
    is_semver,
    is_unchanged,
    version_bump,
)

BASE = {
    "apiVersion": "v3.2.0", "kind": "DataContract",
    "id": "11111111-1111-1111-1111-111111111111",
    "name": "Sales Orders", "version": "1.0.0", "status": "active",
    "domain": "commerce", "team": {"name": "commerce-team"},
    "description": {"purpose": "Orders placed"},
    "customProperties": [{"property": "tier", "value": 2}],
    "schema": [{
        "name": "sales_orders", "logicalType": "object", "physicalType": "table",
        "properties": [
            {"name": "order_id", "logicalType": "string", "description": "Order key",
             "required": True, "primaryKey": True},
            {"name": "amount", "logicalType": "number", "description": "Gross value",
             "required": False,
             "quality": [{"type": "library", "metric": "nullValues",
                          "mustBeLessOrEqualTo": 1, "unit": "percent",
                          "dimension": "completeness"}]},
            {"name": "placed_at", "logicalType": "timestamp",
             "description": "Placement time", "required": True},
        ],
    }],
    "slaProperties": [{"property": "freshness", "value": 24, "unit": "h"},
                      {"property": "availability", "value": 99.9, "unit": "%"}],
}
CHANNEL = {"name": "channel", "logicalType": "string"}


def _doc(*mutations, **top):
    doc = copy.deepcopy(BASE)
    doc.update(top)
    for mutate in mutations:
        mutate(doc)
    return doc


def _props(doc):
    return doc["schema"][0]["properties"]


def _prop(doc, name):
    return next(p for p in _props(doc) if p["name"] == name)


def _set(prop_name, **values):
    return lambda d: _prop(d, prop_name).update(values)


def _pop(name, key):
    return lambda d: _prop(d, name).pop(key)


def _remove(name):
    return lambda d: _props(d).remove(_prop(d, name))


def _add(prop):
    return lambda d: _props(d).append(copy.deepcopy(prop))


def _rule(**values):
    return lambda d: _prop(d, "amount")["quality"][0].update(values)


def _reverse(d):
    _props(d).reverse()
    d["slaProperties"].reverse()


def _two_rules(order):
    rules = [{"type": "text", "description": "first"}, {"type": "text", "description": "second"}]

    def mutate(d):
        _prop(d, "amount")["quality"] = [rules[i] for i in order]

    return mutate


def _drop_schema(d):
    d.pop("schema")


def _rename_table(d):
    d["name"] = "Orders"
    d["schema"][0]["name"] = "orders"


CASES = [
    pytest.param(BASE, _doc(), ChangeKind.NONE, id="none-identical"),
    pytest.param(BASE, _doc(version="1.0.1"), ChangeKind.NONE, id="none-version-only"),
    pytest.param(BASE, _doc(status="deprecated"), ChangeKind.NONE, id="none-status-only"),
    pytest.param(BASE, _doc(_reverse), ChangeKind.NONE, id="none-reorder"),
    pytest.param(BASE, _doc(_pop("amount", "required"), _set("order_id", unique=False, classification="")),
                 ChangeKind.NONE, id="none-empties"),
    pytest.param(BASE, _doc(_remove("amount")), ChangeKind.MAJOR, id="major-remove"),
    pytest.param(BASE, _doc(_set("amount", name="gross_amount")), ChangeKind.MAJOR, id="major-rename"),
    pytest.param(BASE, _doc(_set("amount", logicalType="string")), ChangeKind.MAJOR, id="major-type"),
    pytest.param(BASE, _doc(_set("amount", required=True)), ChangeKind.MAJOR, id="major-required-on"),
    pytest.param(BASE, _doc(_drop_schema), ChangeKind.MAJOR, id="major-drop-schema"),
    pytest.param(BASE, _doc(_remove("amount"), _add(CHANNEL)), ChangeKind.MAJOR, id="major-beats-minor"),
    pytest.param(BASE, _doc(_add(CHANNEL)), ChangeKind.MINOR, id="minor-add"),
    pytest.param(BASE, _doc(_add({**CHANNEL, "required": True})), ChangeKind.MINOR, id="minor-add-required"),
    pytest.param(BASE, _doc(_set("placed_at", required=False)), ChangeKind.MINOR, id="minor-relax-required"),
    pytest.param(_doc(_set("amount", unique=True)), BASE, ChangeKind.MINOR, id="minor-relax-unique"),
    pytest.param(_doc(_drop_schema), BASE, ChangeKind.MINOR, id="minor-first-schema"),
    pytest.param(BASE, _doc(_set("amount", description="Net value")), ChangeKind.PATCH, id="patch-description"),
    pytest.param(BASE, _doc(_rename_table), ChangeKind.PATCH, id="patch-title"),
    pytest.param(BASE, _doc(team={"name": "finance-team"}), ChangeKind.PATCH, id="patch-owner"),
    pytest.param(BASE, _doc(customProperties=[{"property": "tier", "value": 1}]), ChangeKind.PATCH,
                 id="patch-tier"),
    pytest.param(BASE, _doc(slaProperties=[{"property": "freshness", "value": 48, "unit": "h"},
                                           {"property": "availability", "value": 99.9, "unit": "%"}]),
                 ChangeKind.PATCH, id="patch-sla"),
    pytest.param(BASE, _doc(_rule(mustBeLessOrEqualTo=5)), ChangeKind.PATCH, id="patch-quality"),
    pytest.param(BASE, _doc(_set("amount", unique=True)), ChangeKind.PATCH, id="patch-unique-on"),
    pytest.param(BASE, _doc(domain="finance"), ChangeKind.PATCH, id="patch-domain"),
    # Edge rows.
    pytest.param(_doc(_rule(mustBeLessOrEqualTo=0)),
                 _doc(lambda d: _prop(d, "amount")["quality"][0].pop("mustBeLessOrEqualTo")),
                 ChangeKind.PATCH, id="zero-is-a-value"),
    pytest.param(_doc(_two_rules([0, 1])), _doc(_two_rules([1, 0])), ChangeKind.NONE,
                 id="none-quality-reorder"),
    pytest.param(_doc(_drop_schema), _doc(_drop_schema), ChangeKind.NONE, id="none-no-schema"),
    pytest.param(BASE, _doc(tags=["x"]), ChangeKind.PATCH, id="patch-unknown-key"),
    pytest.param(BASE, _doc(apiVersion="v3.1.0", kind="Other",
                            id="22222222-2222-2222-2222-222222222222"),
                 ChangeKind.NONE, id="none-identity-keys"),
    pytest.param(BASE, _doc(_set("amount", primaryKey=True)), ChangeKind.PATCH, id="patch-pk-on"),
    pytest.param(BASE, _doc(_pop("order_id", "primaryKey")), ChangeKind.MINOR, id="minor-pk-off"),
    pytest.param(BASE, _doc(_set("amount", physicalType="DECIMAL(10,2)")), ChangeKind.PATCH,
                 id="patch-physical-type"),
]


@pytest.mark.parametrize("old, new, expected", CASES)
def test_classify_change(old, new, expected):
    assert classify_change(old, new) is expected


def _no_change(d):
    pass


BUMPS = [
    (_add(CHANNEL), "active", "1.0.0", "1.0.0", False),
    (_add(CHANNEL), "active", "1.0.0", "1.0.1", False),
    (_add(CHANNEL), "active", "1.0.0", "1.1.0", True),
    (_add(CHANNEL), "active", "1.0.0", "2.0.0", True),
    (_remove("amount"), "active", "1.0.0", "1.1.0", False),
    (_remove("amount"), "active", "1.0.0", "2.0.0", True),
    (_remove("amount"), "deprecated", "1.0.0", "1.1.0", False),
    (_remove("amount"), "draft", "1.0.0", "1.0.0", True),
    (_remove("amount"), "proposed", "1.0.0", "1.0.0", True),
    (_no_change, "active", "1.0.0", "1.0.0", True),
    (_no_change, "active", "1.0.0", "1.0.1", True),
    (_no_change, "active", "1.1.0", "1.0.0", False),
    (_add(CHANNEL), "active", "1.9.0", "1.10.0", True),
    (_remove("amount"), "active", "1.0", "1.1.0", True),
    (_add(CHANNEL), "active", "1.0", "1.0", False),
]


@pytest.mark.parametrize("change, status, old_version, new_version, allowed", BUMPS)
def test_evolution_violation(change, status, old_version, new_version, allowed):
    old = _doc(status=status, version=old_version)
    new = _doc(change, status=status, version=new_version)
    assert (evolution_violation(old, new) is None) == allowed


def test_status_change_alone_needs_no_bump():
    old = _doc(version="1.0")
    assert evolution_violation(old, _doc(version="1.0", status="deprecated")) is None


def test_rejection_names_the_changes_that_force_the_bump():
    message = evolution_violation(BASE, _doc(_remove("amount"), version="1.1.0"))
    assert message == (
        "Contract changes require a MAJOR version bump"
        " (current 1.0.0, requested 1.1.0): property 'amount' removed"
    )


def test_rejection_lists_only_the_changes_of_the_required_kind():
    message = evolution_violation(
        BASE, _doc(_remove("amount"), _set("order_id", description="x"), version="1.0.1")
    )
    assert message.endswith(": property 'amount' removed")


def test_rejection_of_a_lower_version():
    old = {**BASE, "version": "1.1.0"}
    assert evolution_violation(old, {**BASE, "version": "1.0.0"}) == (
        "Version 1.0.0 is lower than the current version 1.1.0"
    )


@pytest.mark.parametrize("version, expected", [
    ("1.0.0", True), ("10.20.30", True), ("0.0.0", True), ("01.2.3", True),
    ("1.0", False), ("v1.0.0", False), ("1.0.0-rc1", False), ("1.0.0\n", False),
    ("", False), ("١.٠.٠", False), (" 1.0.0", False), (None, False),
])
def test_is_semver(version, expected):
    assert is_semver(version) is expected


def test_version_bump_kinds():
    assert version_bump("1.2.3", "1.2.4") is ChangeKind.PATCH
    assert version_bump("1.2.3", "1.3.0") is ChangeKind.MINOR
    assert version_bump("1.2.3", "2.0.0") is ChangeKind.MAJOR
    assert version_bump("1.2.3", "1.2.3") is ChangeKind.NONE
    assert version_bump("1.2.3", "1.2.2") is ChangeKind.NONE
    assert version_bump("1.0", "1.0.0") is ChangeKind.MAJOR


def test_is_unchanged():
    assert is_unchanged(BASE, copy.deepcopy(BASE))
    assert not is_unchanged(BASE, {**BASE, "version": "1.0.1"})
    assert not is_unchanged(BASE, {**BASE, "status": "deprecated"})
    assert not is_unchanged(BASE, {**BASE, "name": "Other"})


def test_policy_errors_are_not_value_errors():
    # The routers turn ValueError into 400; a policy rejection is a 409.
    assert not issubclass(ContractEvolutionError, ValueError)
