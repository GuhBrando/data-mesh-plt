from backend.infra import config
from backend.interface.dependencies import get_github_client


def test_test_suite_cannot_build_a_real_github_client():
    assert config.GITHUB_TOKEN == ""
    assert get_github_client() is None
