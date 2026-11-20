from typing import Any

import yaml

from backend.domain.entities.data_contract import DataContract
from backend.use_cases.data_contract.odcs import to_odcs

# The C dumper is much faster; both write the same text for plain data.
_DUMPER = getattr(yaml, "CSafeDumper", yaml.SafeDumper)


def dump_odcs(doc: dict[str, Any]) -> str:
    return yaml.dump(
        doc,
        Dumper=_DUMPER,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
    )


def assemble_yaml(contract: DataContract) -> str:
    return dump_odcs(to_odcs(contract))
