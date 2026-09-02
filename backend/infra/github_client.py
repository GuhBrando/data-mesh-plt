import base64
import logging
import re

import httpx

logger = logging.getLogger(__name__)

_API = "https://api.github.com"

PLATFORM_TOPIC = "data-mesh-platform"


class RepoNameUnavailable(RuntimeError):
    """Repo name is taken by a repo the platform must not adopt."""


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


class GitHubClient:
    def __init__(self, token: str, repo: str):
        self._repo = repo
        self._owner = repo.split("/", 1)[0]
        self._owner_type: str | None = None
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

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

    async def push(self, path: str, content: str, message: str) -> None:
        async with httpx.AsyncClient(timeout=10.0) as client:
            sha = await self._get_sha(client, path)
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
        async with httpx.AsyncClient(timeout=10.0) as client:
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

    async def list_all_yaml_contents(self) -> list[tuple[str, str]]:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(
                f"{_API}/repos/{self._repo}/git/trees/HEAD?recursive=1",
                headers=self._headers,
            )
            if r.status_code != 200:
                return []
            tree = r.json().get("tree", [])
            blobs = [
                i
                for i in tree
                if i["path"].startswith("contracts/")
                and i["path"].endswith(".yaml")
                and i["type"] == "blob"
            ]
            results: list[tuple[str, str]] = []
            for item in blobs:
                blob_r = await client.get(item["url"], headers=self._headers)
                if blob_r.status_code == 200:
                    raw = blob_r.json().get("content", "")
                    content = base64.b64decode(raw.replace("\n", "")).decode()
                    results.append((item["path"], content))
            return results

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
        async with httpx.AsyncClient(timeout=15.0) as client:
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
        async with httpx.AsyncClient(timeout=15.0) as client:
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
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.patch(
                f"{_API}/repos/{repo_full_name}",
                headers=self._headers,
                json={"archived": True},
            )
            self._raise_for_status(r)
