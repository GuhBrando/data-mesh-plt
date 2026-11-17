import yaml

from backend.domain.entities.data_contract import DataContract
from backend.use_cases.data_contract.odcs import to_odcs


def assemble_yaml(contract: DataContract) -> str:
    return yaml.dump(
        to_odcs(contract), default_flow_style=False, allow_unicode=True, sort_keys=False
    )
