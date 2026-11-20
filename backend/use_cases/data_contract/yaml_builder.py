import yaml

from backend.domain.entities.data_contract import DataContract
from backend.use_cases.data_contract.odcs import to_odcs

# The C dumper is much faster; both write the same text for plain data.
_DUMPER = getattr(yaml, "CSafeDumper", yaml.SafeDumper)


def assemble_yaml(contract: DataContract) -> str:
    return yaml.dump(
        to_odcs(contract),
        Dumper=_DUMPER,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
    )
