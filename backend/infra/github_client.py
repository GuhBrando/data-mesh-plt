import asyncio
import base64
import logging
import re
from typing import Any, NamedTuple

import httpx

from backend.infra.github_auth import API_HEADERS, BearerTokenAuth

logger = logging.getLogger(__name__)

_API = "https://api.github.com"

PLATFORM_TOPIC = "data-mesh-platform"
_BLOB_CONCURRENCY = 8


class RepoNameUnavailable(RuntimeError):
    """Repo name is taken by a repo the platform must not adopt."""


class ContractFile(NamedTuple):
    path: str
    content: str
    sha: str


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


class GitHubClient:
    def __init__(
        self,
        *,
        repo: str,
        token: str | None = None,
        auth: httpx.Auth | None = None,
    ):
        """Pass either ``token`` (a static bearer token) or ``auth`` (e.g. a
        ``GitHubAppAuth`` shared across requests so its token cache survives)."""
        if (token is None) == (auth is None):
            raise ValueError("GitHubClient needs exactly one of token or auth")
        self._repo = repo
        self._owner = repo.split("/", 1)[0]
        self._owner_type: str | None = None
        self._auth = auth if auth is not None else BearerTokenAuth(token or "")
        self._headers = dict(API_HEADERS)

    def _http(self, timeout: float) -> httpx.AsyncClient:
        # follow_redirects: GitHub answers 301/307 for a renamed or transferred
        # repository, so URLs stored before a transfer keep working. httpx drops
        # the Authorization header on a redirect to another origin.
        return httpx.AsyncClient(
            timeout=timeout, auth=self._auth, follow_redirects=True
        )

    @property
    def repo(self) -> str:
        return self._repo

    def contract_path(self, domain: str, title: str) -> str:
        return f"contracts/{_slugify(domain)}/{_slugify(title)}.yaml"

    async def _get_sha(self, client: httpx.AsyncClient, path: str) -> str | None:
        r = await client.get(
            f"{_API}/repos/{self._repo}/contents/{path}",
            headers=self._headers,
        )
        if r.status_code == 200:
            return r.json().get("sha")
        return None

    @staticmethod
    def _raise_for_status(r: httpx.Response) -> None:
        if not r.is_success:
            raise RuntimeError(f"GitHub API {r.status_code}: {r.text}")

    async def push(
        self,
        path: str,
        content: str,
        message: str,
        expected_sha: str | None = None,
    ) -> None:
        async with self._http(10.0) as client:
            # `is not None`: an empty expected_sha must not fall back to the
            # lookup, which would turn the compare-and-swap into last-writer-wins.
            sha = (
                expected_sha
                if expected_sha is not None
                else await self._get_sha(client, path)
            )
            payload: dict = {
                "message": message,
                "content": base64.b64encode(content.encode()).decode(),
            }
            if sha:
                payload["sha"] = sha
            r = await client.put(
                f"{_API}/repos/{self._repo}/contents/{path}",
                headers=self._headers,
                json=payload,
            )
            self._raise_for_status(r)

    async def delete(self, path: str, message: str) -> None:
        async with self._http(10.0) as client:
            sha = await self._get_sha(client, path)
            if sha is None:
                return
            r = await client.request(
                "DELETE",
                f"{_API}/repos/{self._repo}/contents/{path}",
                headers=self._headers,
                json={"message": message, "sha": sha},
            )
            self._raise_for_status(r)

    async def _fetch_blob(
        self,
        client: httpx.AsyncClient,
        item: dict[str, Any],
        limit: asyncio.Semaphore,
    ) -> ContractFile:
        path, sha = item["path"], item.get("sha")
        if not sha:
            raise RuntimeError(f"GitHub listed {path} without a sha")
        async with limit:
            r = await client.get(item["url"], headers=self._headers)
        self._raise_for_status(r)
        try:
            raw = r.json().get("content", "")
            content = base64.b64decode(raw.replace("\n", "")).decode("utf-8")
        except ValueError as exc:  # bad JSON, bad base64, not UTF-8
            raise RuntimeError(f"{path} is not a readable UTF-8 file: {exc}") from None
        return ContractFile(path, content, sha)

    async def read_contract_files(self) -> list[ContractFile]:
        """Every contract file with its sha. A failed or partial read raises."""
        async with self._http(15.0) as client:
            r = await client.get(
                f"{_API}/repos/{self._repo}/git/trees/HEAD?recursive=1",
                headers=self._headers,
            )
            self._raise_for_status(r)
            body = r.json()
            if body.get("truncated"):
                raise RuntimeError(
                    "GitHub truncated the repository tree; a partial listing"
                    " would be taken for the whole repository"
                )
            items = [
                item
                for item in body.get("tree", [])
                if item.get("type") == "blob"
                and item["path"].startswith("contracts/")
                and item["path"].endswith(".yaml")
            ]
            # Concurrent, bounded to stay clear of GitHub's secondary rate limits.
            limit = asyncio.Semaphore(_BLOB_CONCURRENCY)
            return list(
                await asyncio.gather(
                    *(self._fetch_blob(client, item, limit) for item in items)
                )
            )

    async def list_all_yaml_contents(self) -> list[tuple[str, str]]:
        """(path, content) of every contract file.

        Raises when the read fails, so sync reports a dead token or a renamed
        repository instead of syncing nothing.
        """
        return [(f.path, f.content) for f in await self.read_contract_files()]

    async def _get_owner_type(self, client: httpx.AsyncClient) -> str:
        if self._owner_type is not None:
            return self._owner_type
        r = await client.get(
            f"{_API}/users/{self._owner}",
            headers=self._headers,
        )
        self._raise_for_status(r)
        self._owner_type = r.json().get("type", "User")
        return self._owner_type

    async def create_product_repo(self, name: str, description: str) -> dict:
        async with self._http(15.0) as client:
            owner_type = await self._get_owner_type(client)
            url = (
                f"{_API}/orgs/{self._owner}/repos"
                if owner_type == "Organization"
                else f"{_API}/user/repos"
            )
            payload = {
                "name": name,
                "description": description,
                "private": True,
                "auto_init": False,
            }
            r = await client.post(url, headers=self._headers, json=payload)
            if r.status_code == 422 and "already exists" in r.text:
                existing = await client.get(
                    f"{_API}/repos/{self._owner}/{name}",
                    headers=self._headers,
                )
                self._raise_for_status(existing)
                data = existing.json()
                if data.get("archived") or PLATFORM_TOPIC not in (
                    data.get("topics") or []
                ):
                    raise RepoNameUnavailable(
                        f"{self._owner}/{name} already exists and is not an "
                        "active platform-managed repository"
                    )
                return {
                    "html_url": data["html_url"],
                    "full_name": data["full_name"],
                }
            self._raise_for_status(r)
            data = r.json()
            await self._tag_platform_repo(client, data["full_name"])
            return {
                "html_url": data["html_url"],
                "full_name": data["full_name"],
            }

    async def _tag_platform_repo(
        self, client: httpx.AsyncClient, repo_full_name: str
    ) -> None:
        """Mark the repo as platform-managed. Never fatal: an untagged repo is
        merely refused for adoption later, which is the safe outcome."""
        r = await client.put(
            f"{_API}/repos/{repo_full_name}/topics",
            headers=self._headers,
            json={"names": [PLATFORM_TOPIC]},
        )
        if not r.is_success:
            logger.warning(
                "Failed to tag %s with topic %s: GitHub API %s",
                repo_full_name,
                PLATFORM_TOPIC,
                r.status_code,
            )

    async def push_scaffold(self, repo_full_name: str, files: dict[str, str]) -> None:
        async with self._http(15.0) as client:
            for path, content in files.items():
                sha_r = await client.get(
                    f"{_API}/repos/{repo_full_name}/contents/{path}",
                    headers=self._headers,
                )
                payload: dict = {
                    "message": f"Scaffold {path}",
                    "content": base64.b64encode(content.encode()).decode(),
                }
                if sha_r.status_code == 200:
                    payload["sha"] = sha_r.json().get("sha")
                r = await client.put(
                    f"{_API}/repos/{repo_full_name}/contents/{path}",
                    headers=self._headers,
                    json=payload,
                )
                self._raise_for_status(r)

    async def archive_repo(self, repo_full_name: str) -> None:
        async with self._http(10.0) as client:
            r = await client.patch(
                f"{_API}/repos/{repo_full_name}",
                headers=self._headers,
                json={"archived": True},
            )
            self._raise_for_status(r)
