import pytest

from backend.domain.contract_access import (
    PUBLISHED_STATUSES,
    ContractActor,
    TransitionRefused,
    allowed_transitions,
    can_delete,
    can_edit,
    can_manage_stakeholders,
    can_read,
    check_transition,
)
from backend.domain.value_objects.user_role import UserRole

ADMIN = ContractActor(UserRole.PLATFORM_ADMIN, is_member=False)
OWNER = ContractActor(UserRole.DATA_OWNER, is_member=True)
OUTSIDE_OWNER = ContractActor(UserRole.DATA_OWNER, is_member=False)
STEWARD = ContractActor(UserRole.DATA_STEWARD, is_member=True)
OUTSIDE_STEWARD = ContractActor(UserRole.DATA_STEWARD, is_member=False)
MEMBER_CONSUMER = ContractActor(UserRole.DATA_CONSUMER, is_member=True)
CONSUMER = ContractActor(UserRole.DATA_CONSUMER, is_member=False)
INVITED = ContractActor(UserRole.DATA_CONSUMER, is_member=False, is_stakeholder=True)

ALL_STATUSES = ("draft", "in_review", "active", "deprecated", "retired")


def test_published_statuses():
    assert {"active", "deprecated", "retired"} == PUBLISHED_STATUSES


@pytest.mark.parametrize("status", ["active", "deprecated", "retired"])
@pytest.mark.parametrize("actor", [CONSUMER, OUTSIDE_STEWARD, OUTSIDE_OWNER])
def test_everyone_reads_published(status, actor):
    assert can_read(status, actor)


@pytest.mark.parametrize(
    "actor, expected",
    [
        (ADMIN, True),
        (OWNER, True),
        (STEWARD, True),
        (INVITED, True),
        (OUTSIDE_STEWARD, False),
        (OUTSIDE_OWNER, False),
        (MEMBER_CONSUMER, False),
        (CONSUMER, False),
    ],
)
@pytest.mark.parametrize("status", ["draft", "in_review"])
def test_drafts_are_read_by_the_domain_and_invited(status, actor, expected):
    assert can_read(status, actor) is expected


def test_published_never_goes_back_to_unpublished():
    for status in PUBLISHED_STATUSES:
        for actor in (ADMIN, OWNER, STEWARD):
            assert not set(allowed_transitions(status, actor)) & {"draft", "in_review"}


@pytest.mark.parametrize(
    "status, actor, expected",
    [
        ("draft", STEWARD, ["in_review"]),
        ("draft", OWNER, []),
        ("draft", ADMIN, ["in_review"]),
        ("in_review", STEWARD, ["draft"]),
        ("in_review", OWNER, ["draft", "active"]),
        ("in_review", ADMIN, ["draft", "active"]),
        ("active", OWNER, ["deprecated", "retired"]),
        ("active", STEWARD, []),
        ("active", ADMIN, ["deprecated", "retired"]),
        ("deprecated", OWNER, ["active", "retired"]),
        ("retired", ADMIN, []),
        ("retired", OWNER, []),
        ("in_review", OUTSIDE_STEWARD, []),
        ("in_review", OUTSIDE_OWNER, []),
        ("in_review", INVITED, []),
        ("draft", MEMBER_CONSUMER, []),
    ],
)
def test_allowed_transitions(status, actor, expected):
    assert allowed_transitions(status, actor) == expected


def test_check_transition_allows_a_listed_move():
    check_transition("in_review", "active", OWNER)
    check_transition("draft", "in_review", STEWARD)


def test_check_transition_forbidden_vs_unknown():
    with pytest.raises(TransitionRefused) as forbidden:
        check_transition("in_review", "active", STEWARD)
    assert forbidden.value.forbidden is True
    assert str(forbidden.value) == (
        "You cannot move this contract from in_review to active."
    )
    with pytest.raises(TransitionRefused) as unknown:
        check_transition("active", "draft", ADMIN)
    assert unknown.value.forbidden is False
    assert str(unknown.value) == "A active contract cannot move to draft."


def test_check_transition_to_the_same_status_is_unknown():
    with pytest.raises(TransitionRefused) as same:
        check_transition("draft", "draft", ADMIN)
    assert same.value.forbidden is False


@pytest.mark.parametrize(
    "status, expected",
    [
        ("draft", True),
        ("in_review", False),
        ("active", True),
        ("deprecated", True),
        ("retired", False),
    ],
)
@pytest.mark.parametrize("actor", [STEWARD, ADMIN])
def test_can_edit_by_status(actor, status, expected):
    assert can_edit(status, actor) is expected


@pytest.mark.parametrize("actor", [OWNER, OUTSIDE_STEWARD, MEMBER_CONSUMER, INVITED])
@pytest.mark.parametrize("status", ALL_STATUSES)
def test_only_the_domain_steward_and_admin_edit(actor, status):
    assert can_edit(status, actor) is False


@pytest.mark.parametrize(
    "actor, expected",
    [
        (ADMIN, True),
        (OWNER, True),
        (OUTSIDE_OWNER, False),
        (STEWARD, False),
        (MEMBER_CONSUMER, False),
    ],
)
def test_can_delete(actor, expected):
    assert can_delete(actor) is expected


@pytest.mark.parametrize(
    "status, actor, expected",
    [
        ("draft", STEWARD, True),
        ("in_review", STEWARD, True),
        ("draft", ADMIN, True),
        ("in_review", ADMIN, True),
        ("active", STEWARD, False),
        ("deprecated", ADMIN, False),
        ("retired", ADMIN, False),
        ("draft", OWNER, False),
        ("draft", OUTSIDE_STEWARD, False),
        ("draft", INVITED, False),
    ],
)
def test_can_manage_stakeholders(status, actor, expected):
    assert can_manage_stakeholders(status, actor) is expected
