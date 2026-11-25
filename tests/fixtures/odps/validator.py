"""The ODPS v1.1.0 JSON schema, loaded once for every check of a product document.

Run as a module to validate YAML files, as CI does:

  python -m tests.fixtures.odps.validator product.odps.yaml [...]
"""

import json
import sys
from pathlib import Path

import jsonschema
import yaml

SCHEMA_FILE = Path(__file__).with_name("odps-json-schema-v1.1.0.json")
VALIDATOR = jsonschema.Draft201909Validator(
    json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))
)


def problems(doc: dict) -> list[str]:
    """Schema errors plus the prose rules the schema does not encode."""
    found = [f"{'/'.join(map(str, e.path)) or '<root>'}: {e.message}" for e in VALIDATOR.iter_errors(doc)]
    if not doc.get("outputPorts"):
        found.append("outputPorts: a data product needs at least one output port")
    if doc.get("status") not in ("proposed", "draft", "active", "deprecated", "retired"):
        found.append(f"status: {doc.get('status')!r} is not an ODPS status")
    return found


if __name__ == "__main__":
    failed = False
    for name in sys.argv[1:]:
        errors = problems(yaml.safe_load(Path(name).read_text(encoding="utf-8")))
        for error in errors:
            print(f"{name}: {error}")
        print(f"{name}: {'invalid' if errors else 'valid'} ODPS v1.1.0")
        failed = failed or bool(errors)
    sys.exit(1 if failed else 0)
