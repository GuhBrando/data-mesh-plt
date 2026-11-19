"""The ODCS v3.2.0 JSON schema, loaded once for every test that checks a document."""

import json
from pathlib import Path

import jsonschema

_SCHEMA = Path(__file__).with_name("odcs-json-schema-v3.2.0.json")
VALIDATOR = jsonschema.Draft201909Validator(json.loads(_SCHEMA.read_text(encoding="utf-8")))
