"""Which service levels the platform stores. Pure: no I/O, no backend imports.

The API and both file readers apply these, so a contract the API accepts can
always be written to a file and synced back.
"""

import math
from collections.abc import Mapping
from typing import Any


def _value_problem(value: Any) -> str | None:
    if isinstance(value, str):
        return None if value.strip() else "a text value cannot be blank"
    if isinstance(value, bool) or not isinstance(value, int | float):
        return "value must be a number or text"
    # JSONB has no NaN or Infinity: storing one would fail the whole write.
    return None if math.isfinite(value) else "value must be a finite number"


def service_level_problems(properties: list[Mapping[str, Any]]) -> list[str]:
    """One message per problem; a property name appears at most once."""
    problems = []
    seen: set[str] = set()
    for prop in properties:
        name = prop.get("property")
        if not isinstance(name, str) or not name.strip():
            problems.append("a service level needs a property name")
            continue
        problem = _value_problem(prop.get("value"))
        if problem:
            problems.append(f"service level {name}: {problem}")
        unit = prop.get("unit")
        if unit is not None and (not isinstance(unit, str) or not unit.strip()):
            problems.append(f"service level {name}: unit must be text")
        if name in seen:
            problems.append(f"service level {name} appears more than once")
        seen.add(name)
    return problems
