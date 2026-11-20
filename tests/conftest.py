import os
from collections.abc import Callable
from unittest.mock import AsyncMock, MagicMock

import pytest

# Provide a deterministic JWT secret for the test suite before any backend
# module (which binds JWT_SECRET_KEY at import time) is loaded. This runs at
# conftest import, ahead of test modules importing the backend. setdefault keeps
# any real value from the environment/.env, while guaranteeing a non-empty key
# in CI — PyJWT >=2.13 raises InvalidKeyError on an empty HMAC key. 32+ bytes
# also satisfies the SHA256 minimum-length recommendation.
os.environ.setdefault(
    "JWT_SECRET_KEY", "test-jwt-secret-key-not-for-production-use-only"
)

# Keep the suite away from the real contracts repository. Router tests that do not
# override get_github_client would otherwise push to and delete from GITHUB_REPO
# with the token in .env.
os.environ["GITHUB_TOKEN"] = ""


class _QueryGuard:
    def __init__(self, mock: AsyncMock) -> None:
        self._mock = mock

    def assert_max_calls(self, method_name: str, max_calls: int = 1) -> None:
        method = getattr(self._mock, method_name)
        count = method.call_count
        if count > max_calls:
            raise AssertionError(
                f"N+1 detected: '{method_name}' called {count} times "
                f"(max allowed: {max_calls})"
            )


@pytest.fixture
def n1_guard() -> Callable[[AsyncMock], _QueryGuard]:
    def _make(mock: AsyncMock) -> _QueryGuard:
        return _QueryGuard(mock)

    return _make


@pytest.fixture
def contract_repo() -> AsyncMock:
    """Repository double whose transaction() works in `async with`."""
    repo = AsyncMock()
    repo.transaction = MagicMock()
    return repo
