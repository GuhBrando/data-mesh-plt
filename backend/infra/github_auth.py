"""Authentication for the GitHub REST API.

Two modes, both exposed as ``httpx.Auth`` so ``GitHubClient`` does not care which
one is active:

- ``BearerTokenAuth``: a static token (personal access token). Legacy fallback.
- ``GitHubAppAuth``: a GitHub App installation token. The App's private key lives
  in Azure Key Vault and never leaves it: the backend asks Key Vault to sign the
  App JWT (authenticating with its managed identity), exchanges the JWT for an
  installation token valid for one hour, and caches that token.
"""

import asyncio
import base64
import hashlib
import json
import logging
import time
from collections.abc import AsyncGenerator, Callable, Generator
from datetime import datetime
from typing import Protocol

import httpx
from azure.identity import DefaultAzureCredential
from azure.keyvault.keys.crypto import CryptographyClient, SignatureAlgorithm

logger = logging.getLogger(__name__)

GITHUB_API_HOST = "api.github.com"
_API = f"https://{GITHUB_API_HOST}"
API_HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

# GitHub rejects App JWTs that live longer than 10 minutes. Backdating `iat`
# absorbs clock drift between this host and GitHub.
_JWT_BACKDATE_SECONDS = 60
_JWT_LIFETIME_SECONDS = 9 * 60
# Renew the installation token this long before GitHub expires it, so a request
# never leaves with a token that dies in flight.
_TOKEN_REFRESH_MARGIN_SECONDS = 5 * 60


class _SyncFlowUnsupported(httpx.Auth):
    def sync_auth_flow(
        self, request: httpx.Request
    ) -> Generator[httpx.Request, httpx.Response, None]:
        raise RuntimeError(f"{type(self).__name__} only supports httpx.AsyncClient")


def _for_github_api(request: httpx.Request) -> bool:
    """Credentials go to the GitHub API host only, never to a URL taken from a
    response body that points elsewhere."""
    return request.url.scheme == "https" and request.url.host == GITHUB_API_HOST


class BearerTokenAuth(_SyncFlowUnsupported):
    """Static token, e.g. a personal access token."""

    def __init__(self, token: str) -> None:
        self._token = token

    async def async_auth_flow(
        self, request: httpx.Request
    ) -> AsyncGenerator[httpx.Request, httpx.Response]:
        if _for_github_api(request):
            request.headers["Authorization"] = f"Bearer {self._token}"
        yield request


class JwtSigner(Protocol):
    async def sign_rs256(self, message: bytes) -> bytes:
        """RSASSA-PKCS1-v1_5 SHA-256 signature of ``message``."""
        ...


class KeyVaultSigner:
    """Signs with an RSA key held in Azure Key Vault. The private key never
    leaves the vault; the caller needs the ``sign`` key permission (the
    "Key Vault Crypto User" role).

    ``key_id`` should be versionless (``https://<vault>.vault.azure.net/keys/<name>``)
    so a key rotated by importing a new version is picked up without a restart.
    """

    def __init__(self, key_id: str, credential: object | None = None) -> None:
        self._key_id = key_id
        # DefaultAzureCredential resolves to the managed identity in Azure and to
        # the developer's `az login` session locally.
        self._credential = credential or DefaultAzureCredential()

    def _sign_sync(self, digest: bytes) -> bytes:
        # A fresh client per signature: one call per hour, and it resolves the
        # latest key version every time instead of pinning the first one seen.
        client = CryptographyClient(self._key_id, credential=self._credential)
        return client.sign(SignatureAlgorithm.rs256, digest).signature

    async def sign_rs256(self, message: bytes) -> bytes:
        digest = hashlib.sha256(message).digest()
        return await asyncio.to_thread(self._sign_sync, digest)


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_json(obj: dict) -> str:
    return _b64url(json.dumps(obj, separators=(",", ":")).encode())


class GitHubAppAuth(_SyncFlowUnsupported):
    """Authenticates as a GitHub App installation.

    ``client_id`` is the App's Client ID (GitHub accepts it as the JWT issuer in
    place of the numeric App ID).
    """

    def __init__(
        self,
        client_id: str,
        installation_id: str,
        signer: JwtSigner,
        *,
        clock: Callable[[], float] = time.time,
        http_client_factory: Callable[[], httpx.AsyncClient] | None = None,
    ) -> None:
        self._client_id = client_id
        self._installation_id = installation_id
        self._signer = signer
        self._clock = clock
        self._http_client_factory = http_client_factory or (
            lambda: httpx.AsyncClient(timeout=10.0)
        )
        self._token: str | None = None
        self._expires_at = 0.0
        self._lock = asyncio.Lock()

    async def _app_jwt(self) -> str:
        now = int(self._clock())
        header = _b64url_json({"alg": "RS256", "typ": "JWT"})
        payload = _b64url_json(
            {
                "iat": now - _JWT_BACKDATE_SECONDS,
                "exp": now + _JWT_LIFETIME_SECONDS,
                "iss": self._client_id,
            }
        )
        signing_input = f"{header}.{payload}"
        signature = await self._signer.sign_rs256(signing_input.encode())
        return f"{signing_input}.{_b64url(signature)}"

    async def _request_installation_token(self) -> tuple[str, float]:
        jwt = await self._app_jwt()
        async with self._http_client_factory() as client:
            r = await client.post(
                f"{_API}/app/installations/{self._installation_id}/access_tokens",
                headers={**API_HEADERS, "Authorization": f"Bearer {jwt}"},
            )
        if r.status_code != 201:
            raise RuntimeError(
                f"GitHub App installation token request failed: {r.status_code}:"
                f" {r.text}"
            )
        body = r.json()
        expires_at = datetime.fromisoformat(body["expires_at"]).timestamp()
        return body["token"], expires_at

    def _token_is_fresh(self) -> bool:
        return (
            self._token is not None
            and self._clock() < self._expires_at - _TOKEN_REFRESH_MARGIN_SECONDS
        )

    async def token(self) -> str:
        """A valid installation token, fetching a new one when needed."""
        if self._token_is_fresh():
            return self._token  # type: ignore[return-value]
        async with self._lock:
            # Another request may have refreshed the token while this one waited.
            if not self._token_is_fresh():
                self._token, self._expires_at = await self._request_installation_token()
                logger.info("Obtained a GitHub App installation token")
            return self._token  # type: ignore[return-value]

    def invalidate(self, rejected: str) -> None:
        """Drop the cached token if it is the one GitHub just rejected."""
        if self._token == rejected:
            self._token = None
            self._expires_at = 0.0

    async def async_auth_flow(
        self, request: httpx.Request
    ) -> AsyncGenerator[httpx.Request, httpx.Response]:
        if not _for_github_api(request):
            yield request
            return
        token = await self.token()
        request.headers["Authorization"] = f"Bearer {token}"
        response = yield request
        if response.status_code == 401:
            # Revoked before its expiry (e.g. the installation was suspended or
            # the App's key rotated). One retry with a fresh token.
            self.invalidate(token)
            request.headers["Authorization"] = f"Bearer {await self.token()}"
            yield request


def build_github_auth(
    *,
    token: str,
    app_client_id: str,
    app_installation_id: str,
    app_key_vault_key_id: str,
    signer_factory: Callable[[str], JwtSigner] = KeyVaultSigner,
) -> httpx.Auth | None:
    """Pick the GitHub credentials from configuration.

    The GitHub App wins when it is fully configured. A partial App configuration
    is logged and ignored, so a deploy that misses one variable keeps working on
    the token instead of losing GitHub integration.
    """
    app_settings = {
        "GITHUB_APP_CLIENT_ID": app_client_id,
        "GITHUB_APP_INSTALLATION_ID": app_installation_id,
        "GITHUB_APP_KEY_VAULT_KEY_ID": app_key_vault_key_id,
    }
    configured = [name for name, value in app_settings.items() if value]
    if len(configured) == len(app_settings):
        return GitHubAppAuth(
            app_client_id, app_installation_id, signer_factory(app_key_vault_key_id)
        )
    if configured:
        missing = sorted(set(app_settings) - set(configured))
        logger.error(
            "GitHub App partially configured (missing %s); %s",
            ", ".join(missing),
            "falling back to GITHUB_TOKEN" if token else "GitHub integration is off",
        )
    if token:
        return BearerTokenAuth(token)
    return None
