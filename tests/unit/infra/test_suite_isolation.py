from backend.infra import config
from backend.interface.dependencies import get_github_client


def test_test_suite_cannot_build_a_real_github_client():
    assert config.GITHUB_TOKEN == ""
    assert config.GITHUB_APP_CLIENT_ID == ""
    assert config.GITHUB_APP_INSTALLATION_ID == ""
    assert config.GITHUB_APP_KEY_VAULT_KEY_ID == ""
    assert get_github_client() is None
