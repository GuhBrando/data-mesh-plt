import asyncio
import hashlib
import logging
import sys
import types
from datetime import UTC, datetime

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.asymmetric.utils import Prehashed

from backend.infra.github_auth import (
    BearerTokenAuth,
    GitHubAppAuth,
    KeyVaultSigner,
    build_github_auth,
)

CLIENT_ID = "Iv23testclientid"
INSTALLATION_ID = "42"
TOKEN_URL = f"https://api.github.com/app/installations/{INSTALLATION_ID}/access_tokens"
KEY_ID = "https://dmplt-kv.vault.azure.net/keys/github-app"


@pytest.fixture(scope="module")
def rsa_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


class FakeKeyVaultCryptographyClient:
    """Stands in for azure's CryptographyClient. Like Key Vault, it signs a
    SHA-256 digest it is handed, never the message itself."""

    calls: list[tuple[str, object, bytes]] = []
    private_key: rsa.RSAPrivateKey

    def __init__(self, key_id, credential):
        self._key_id = key_id
        self._credential = credential

    def sign(self, algorithm, digest):
        assert algorithm == "RS256"
        type(self).calls.append((self._key_id, self._credential, digest))
        signature = self.private_key.sign(
            digest, padding.PKCS1v15(), Prehashed(hashes.SHA256())
        )
        return types.SimpleNamespace(signature=signature)


class FakeDefaultAzureCredential:
    created = 0

    def __init__(self):
        type(self).created += 1


@pytest.fixture
def key_vault(rsa_key, monkeypatch):
    """A fake Azure SDK in sys.modules, which the signer's lazy imports resolve to.

    No test loads the real SDK: importing it takes about a second, and mutmut runs
    the unit suite once per mutant.
    """
    FakeKeyVaultCryptographyClient.calls = []
    FakeKeyVaultCryptographyClient.private_key = rsa_key
    FakeDefaultAzureCredential.created = 0
    crypto = types.ModuleType("azure.keyvault.keys.crypto")
    crypto.CryptographyClient = FakeKeyVaultCryptographyClient
    crypto.SignatureAlgorithm = types.SimpleNamespace(rs256="RS256")
    identity = types.ModuleType("azure.identity")
    identity.DefaultAzureCredential = FakeDefaultAzureCredential
    for name in ("azure", "azure.keyvault", "azure.keyvault.keys"):
        monkeypatch.setitem(sys.modules, name, types.ModuleType(name))
    monkeypatch.setitem(sys.modules, "azure.keyvault.keys.crypto", crypto)
    monkeypatch.setitem(sys.modules, "azure.identity", identity)
    return FakeKeyVaultCryptographyClient


class LocalSigner:
    def __init__(self, private_key):
        self._key = private_key

    async def sign_rs256(self, message: bytes) -> bytes:
        return self._key.sign(message, padding.PKCS1v15(), hashes.SHA256())


class Clock:
    def __init__(self, now: float):
        self.now = now

    def __call__(self) -> float:
        return self.now


class FakeGitHub:
    """Token endpoint plus an API endpoint that accepts only listed tokens."""

    def __init__(self, tokens: list[str], ttl: int = 3600, clock=None):
        self._tokens = list(tokens)
        self._ttl = ttl
        self._clock = clock
        self.token_requests: list[httpx.Request] = []
        self.api_requests: list[httpx.Request] = []
        # Header values as sent. A retried request is the same object with its
        # header rewritten, so reading it back afterwards shows the last value.
        self.api_auth: list[str | None] = []
        self.rejected: set[str] = set()

    async def handler(self, request: httpx.Request) -> httpx.Response:
        if request.url == TOKEN_URL and request.method == "POST":
            self.token_requests.append(request)
            await asyncio.sleep(0)  # let concurrent callers pile up
            now = self._clock() if self._clock else datetime.now(UTC).timestamp()
            expires = datetime.fromtimestamp(now + self._ttl, UTC)
            return httpx.Response(
                201,
                json={
                    "token": self._tokens.pop(0),
                    "expires_at": expires.strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
            )
        self.api_requests.append(request)
        self.api_auth.append(request.headers.get("Authorization"))
        auth = request.headers.get("Authorization", "")
        if auth.removeprefix("Bearer ") in self.rejected:
            return httpx.Response(401, json={"message": "Bad credentials"})
        return httpx.Response(200, json={"ok": True})

    def client_factory(self):
        return lambda: httpx.AsyncClient(transport=httpx.MockTransport(self.handler))


def _app_auth(github: FakeGitHub, signer, clock=None) -> GitHubAppAuth:
    kwargs = {"http_client_factory": github.client_factory()}
    if clock is not None:
        kwargs["clock"] = clock
    return GitHubAppAuth(CLIENT_ID, INSTALLATION_ID, signer, **kwargs)


# --- App JWT ---------------------------------------------------------------


async def test_app_jwt_signed_through_key_vault_verifies_with_the_public_key(
    rsa_key, key_vault
):
    signer = KeyVaultSigner(KEY_ID, credential="managed-identity")
    auth = GitHubAppAuth(CLIENT_ID, INSTALLATION_ID, signer)

    token = await auth._app_jwt()

    claims = jwt.decode(token, rsa_key.public_key(), algorithms=["RS256"])
    assert claims["iss"] == CLIENT_ID
    assert claims["exp"] - claims["iat"] == 600
    assert jwt.get_unverified_header(token) == {"alg": "RS256", "typ": "JWT"}
    # Key Vault received the digest of the signing input, for the configured key.
    signing_input = token.rsplit(".", 1)[0].encode()
    assert key_vault.calls == [
        (KEY_ID, "managed-identity", hashlib.sha256(signing_input).digest())
    ]


async def test_app_jwt_is_backdated_and_lives_under_ten_minutes(rsa_key):
    clock = Clock(1_800_000_000)
    auth = GitHubAppAuth(CLIENT_ID, INSTALLATION_ID, LocalSigner(rsa_key), clock=clock)

    token = await auth._app_jwt()

    claims = jwt.decode(
        token,
        rsa_key.public_key(),
        algorithms=["RS256"],
        options={"verify_exp": False, "verify_iat": False},
    )
    assert claims["iat"] == clock.now - 60
    assert claims["exp"] == clock.now + 540


async def test_key_vault_signer_creates_the_default_credential_once(key_vault):
    signer = KeyVaultSigner(KEY_ID)
    assert FakeDefaultAzureCredential.created == 0  # nothing loaded until needed

    await signer.sign_rs256(b"a")
    await signer.sign_rs256(b"b")

    assert FakeDefaultAzureCredential.created == 1
    assert all(isinstance(c[1], FakeDefaultAzureCredential) for c in key_vault.calls)


def test_importing_the_app_does_not_load_the_azure_sdk():
    # Every pytest run (once per mutant under mutmut) would pay for it.
    import backend.interface.dependencies  # noqa: F401

    assert [m for m in sys.modules if m == "azure" or m.startswith("azure.")] == []


async def test_key_vault_signer_resolves_the_key_on_every_signature(key_vault):
    signer = KeyVaultSigner(KEY_ID, credential="mi")

    await signer.sign_rs256(b"a")
    await signer.sign_rs256(b"b")

    # A fresh client each time, so a rotated key version is picked up.
    assert [c[2] for c in key_vault.calls] == [
        hashlib.sha256(b"a").digest(),
        hashlib.sha256(b"b").digest(),
    ]


# --- Installation token ----------------------------------------------------


async def test_installation_token_is_requested_with_the_app_jwt(rsa_key):
    github = FakeGitHub(["ghs_1"])
    auth = _app_auth(github, LocalSigner(rsa_key))

    assert await auth.token() == "ghs_1"

    [request] = github.token_requests
    app_jwt = request.headers["Authorization"].removeprefix("Bearer ")
    assert jwt.decode(app_jwt, rsa_key.public_key(), algorithms=["RS256"])[
        "iss"
    ] == (CLIENT_ID)
    assert request.headers["X-GitHub-Api-Version"] == "2022-11-28"


async def test_installation_token_is_cached_until_close_to_expiry(rsa_key):
    clock = Clock(1_800_000_000)
    github = FakeGitHub(["ghs_1", "ghs_2"], ttl=3600, clock=clock)
    auth = _app_auth(github, LocalSigner(rsa_key), clock=clock)

    assert await auth.token() == "ghs_1"
    clock.now += 3600 - 301  # still more than 5 minutes left
    assert await auth.token() == "ghs_1"
    clock.now += 2  # now inside the 5-minute refresh margin
    assert await auth.token() == "ghs_2"
    assert len(github.token_requests) == 2


async def test_concurrent_callers_share_one_token_request(rsa_key):
    github = FakeGitHub(["ghs_1", "ghs_2"])
    auth = _app_auth(github, LocalSigner(rsa_key))

    tokens = await asyncio.gather(*(auth.token() for _ in range(5)))

    assert tokens == ["ghs_1"] * 5
    assert len(github.token_requests) == 1


async def test_failed_token_request_raises_with_the_status(rsa_key):
    def handler(request):
        return httpx.Response(401, json={"message": "A JSON web token could not"})

    auth = GitHubAppAuth(
        CLIENT_ID,
        INSTALLATION_ID,
        LocalSigner(rsa_key),
        http_client_factory=lambda: httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ),
    )

    with pytest.raises(RuntimeError, match="401"):
        await auth.token()


# --- Auth flow -------------------------------------------------------------


async def test_app_auth_sends_the_installation_token_to_the_api(rsa_key):
    github = FakeGitHub(["ghs_1"])
    auth = _app_auth(github, LocalSigner(rsa_key))

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(github.handler), auth=auth
    ) as client:
        r = await client.get("https://api.github.com/repos/acme/x")

    assert r.status_code == 200
    assert github.api_auth == ["Bearer ghs_1"]


async def test_app_auth_retries_once_with_a_new_token_after_401(rsa_key):
    github = FakeGitHub(["ghs_revoked", "ghs_fresh"])
    github.rejected.add("ghs_revoked")
    auth = _app_auth(github, LocalSigner(rsa_key))

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(github.handler), auth=auth
    ) as client:
        r = await client.get("https://api.github.com/repos/acme/x")

    assert r.status_code == 200
    assert github.api_auth == [
        "Bearer ghs_revoked",
        "Bearer ghs_fresh",
    ]


async def test_app_auth_gives_up_after_one_retry(rsa_key):
    github = FakeGitHub(["ghs_a", "ghs_b", "ghs_c"])
    github.rejected.update({"ghs_a", "ghs_b", "ghs_c"})
    auth = _app_auth(github, LocalSigner(rsa_key))

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(github.handler), auth=auth
    ) as client:
        r = await client.get("https://api.github.com/repos/acme/x")

    assert r.status_code == 401
    assert len(github.api_requests) == 2


@pytest.mark.parametrize(
    "url", ["https://example.com/repos/acme/x", "http://api.github.com/repos/acme/x"]
)
async def test_credentials_never_leave_for_another_host_or_plain_http(rsa_key, url):
    github = FakeGitHub(["ghs_1"])
    app = _app_auth(github, LocalSigner(rsa_key))

    for auth in (app, BearerTokenAuth("ghp_static")):
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(github.handler), auth=auth
        ) as client:
            await client.get(url)

    assert github.api_auth == [None, None]
    assert github.token_requests == []


async def test_bearer_token_auth_sends_the_static_token():
    github = FakeGitHub([])
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(github.handler),
        auth=BearerTokenAuth("ghp_static"),
    ) as client:
        await client.get("https://api.github.com/user")

    assert github.api_auth == ["Bearer ghp_static"]


def test_sync_clients_are_refused():
    with (
        httpx.Client(auth=BearerTokenAuth("t")) as client,
        pytest.raises(RuntimeError, match="AsyncClient"),
    ):
        client.get("https://api.github.com/user")


# --- Selection from configuration ------------------------------------------


def _build(**overrides):
    settings = {
        "token": "",
        "app_client_id": "",
        "app_installation_id": "",
        "app_key_vault_key_id": "",
        "signer_factory": lambda key_id: LocalSigner(None),
    }
    settings.update(overrides)
    return build_github_auth(**settings)


def test_fully_configured_app_wins_over_the_token():
    seen = []
    auth = _build(
        token="ghp_x",
        app_client_id=CLIENT_ID,
        app_installation_id=INSTALLATION_ID,
        app_key_vault_key_id=KEY_ID,
        signer_factory=lambda key_id: seen.append(key_id) or LocalSigner(None),
    )

    assert isinstance(auth, GitHubAppAuth)
    assert seen == [KEY_ID]


def test_token_alone_gives_bearer_auth():
    assert isinstance(_build(token="ghp_x"), BearerTokenAuth)


def test_nothing_configured_disables_github():
    assert _build() is None


def test_partial_app_config_falls_back_to_the_token_and_logs(caplog):
    with caplog.at_level(logging.ERROR, logger="backend.infra.github_auth"):
        auth = _build(token="ghp_x", app_client_id=CLIENT_ID)

    assert isinstance(auth, BearerTokenAuth)
    assert "GITHUB_APP_INSTALLATION_ID" in caplog.text
    assert "GITHUB_APP_KEY_VAULT_KEY_ID" in caplog.text
    assert "falling back to GITHUB_TOKEN" in caplog.text


def test_partial_app_config_without_token_disables_github(caplog):
    with caplog.at_level(logging.ERROR, logger="backend.infra.github_auth"):
        auth = _build(app_installation_id=INSTALLATION_ID)

    assert auth is None
    assert "GitHub integration is off" in caplog.text
