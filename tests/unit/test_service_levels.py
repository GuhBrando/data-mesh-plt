import pytest

from backend.domain.service_levels import service_level_problems


def test_numbers_with_units_and_text_are_accepted():
    assert service_level_problems([
        {"property": "freshness", "value": 24, "unit": "h"},
        {"property": "availability", "value": 99.9, "unit": "%"},
        {"property": "retention", "value": "P1D", "unit": None},
    ]) == []


@pytest.mark.parametrize(("properties", "fragment"), [
    ([{"property": "freshness", "value": 1, "unit": "h"}, {"property": "freshness", "value": 2, "unit": "h"}],
     "freshness appears more than once"),
    ([{"property": "latency", "value": float("nan")}], "finite"),
    ([{"property": "latency", "value": float("-inf")}], "finite"),
    ([{"property": "frequency", "value": " "}], "blank"),
    ([{"property": "frequency", "value": True}], "number or text"),
    ([{"property": "frequency", "value": None}], "number or text"),
    ([{"property": "frequency", "value": 1, "unit": 7}], "unit must be text"),
    ([{"property": "frequency", "value": 1, "unit": " "}], "unit must be text"),
    ([{"property": 5, "value": 1}], "property name"),
    ([{"property": " ", "value": 1}], "property name"),
])
def test_what_cannot_be_stored_or_synced_back_is_named(properties, fragment):
    [problem] = service_level_problems(properties)
    assert fragment in problem
