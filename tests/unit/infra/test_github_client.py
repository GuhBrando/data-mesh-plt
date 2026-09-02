import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from backend.infra.github_client import (
    PLATFORM_TOPIC,
    GitHubClient,
    RepoNameUnavailable,
)


def _resp(status: int, json_body: dict | None = None) -> MagicMock:
    r = MagicMock(spec=httpx.Response)
    r.status_code = status
    r.is_success = 200 <= status < 300
    body = json_body if json_body is not None else {}
    r.json.return_value = body
    r.text = json.dumps(body)
    return r


@pytest.fixture
def client():
    return GitHubClient(token="t", repo="acme/contracts")


def _async_client_ctx(mock_client):
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_client)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx


async def test_create_product_repo_user_owner_posts_to_user_repos(client):
    mock_http = AsyncMock()
    mock_http.get = AsyncMock(
        return_value=_resp(200, {"type": "User", "login": "acme"})
    )
    mock_http.post = AsyncMock(
        return_value=_resp(
            201, {"html_url": "https://github.com/acme/dp-x", "full_name": "acme/dp-x"}
        )
    )
    with patch(
        "backend.infra.github_client.httpx.AsyncClient",
        return_value=_async_client_ctx(mock_http),
    ):
        result = await client.create_product_repo("dp-x", "desc")
    assert result["html_url"] == "https://github.com/acme/dp-x"
    assert result["full_name"] == "acme/dp-x"
    mock_http.post.assert_awaited_once()
    posted_url = mock_http.post.await_args.args[0]
    assert posted_url.endswith("/user/repos")


async def test_create_product_repo_org_owner_posts_to_orgs_repos(client):
    mock_http = AsyncMock()
    mock_http.get = AsyncMock(
        return_value=_resp(200, {"type": "Organization", "login": "acme"})
    )
    mock_http.post = AsyncMock(
        return_value=_resp(
            201, {"html_url": "https://github.com/acme/dp-x", "full_name": "acme/dp-x"}
        )
    )
    with patch(
        "backend.infra.github_client.httpx.AsyncClient",
        return_value=_async_client_ctx(mock_http),
    ):
        await client.create_product_repo("dp-x", "desc")
    posted_url = mock_http.post.await_args.args[0]
    assert posted_url.endswith("/orgs/acme/repos")


async def test_create_product_repo_owner_type_cached(client):
    mock_http = AsyncMock()
    mock_http.get = AsyncMock(
        return_value=_resp(200, {"type": "User", "login": "acme"})
    )
    mock_http.post = AsyncMock(
        return_value=_resp(
            201, {"html_url": "https://github.com/acme/dp-x", "full_name": "acme/dp-x"}
        )
    )
    with patch(
        "backend.infra.github_client.httpx.AsyncClient",
        return_value=_async_client_ctx(mock_http),
    ):
        await client.create_product_repo("dp-x", "desc")
        await client.create_product_repo("dp-y", "desc")
    # Owner-detection GET should happen only once across both calls.
    assert mock_http.get.await_count == 1


def _existing_repo(**kw) -> dict:
    return {
        "html_url": "https://github.com/acme/dp-x",
        "full_name": "acme/dp-x",
        "archived": kw.get("archived", False),
        "topics": kw.get("topics", [PLATFORM_TOPIC]),
    }


def _name_taken_client(existing: dict) -> AsyncMock:
    mock_http = AsyncMock()
    mock_http.get = AsyncMock(
        side_effect=[
            _resp(200, {"type": "User", "login": "acme"}),
            _resp(200, existing),
        ]
    )
    mock_http.post = AsyncMock(
        return_value=_resp(422, {"errors": [{"message": "name already exists"}]})
    )
    mock_http.put = AsyncMock(return_value=_resp(200, {}))
    return mock_http


async def test_create_product_repo_adopts_existing_platform_repo_on_422(client):
    mock_http = _name_taken_client(_existing_repo())
    with patch(
        "backend.infra.github_client.httpx.AsyncClient",
        return_value=_async_client_ctx(mock_http),
    ):
        result = await client.create_product_repo("dp-x", "desc")
    assert result["full_name"] == "acme/dp-x"


async def test_create_product_repo_refuses_to_adopt_archived_repo(client):
    mock_http = _name_taken_client(_existing_repo(archived=True))
    with patch(
        "backend.infra.github_client.httpx.AsyncClient",
        return_value=_async_client_ctx(mock_http),
    ):
        with pytest.raises(RepoNameUnavailable):
            await client.create_product_repo("dp-x", "desc")


async def test_create_product_repo_refuses_to_adopt_foreign_repo(client):
    mock_http = _name_taken_client(_existing_repo(topics=["unrelated"]))
    with patch(
        "backend.infra.github_client.httpx.AsyncClient",
        return_value=_async_client_ctx(mock_http),
    ):
        with pytest.raises(RepoNameUnavailable):
            await client.create_product_repo("dp-x", "desc")


async def test_create_product_repo_tags_new_repo_with_platform_topic(client):
    mock_http = AsyncMock()
    mock_http.get = AsyncMock(
        return_value=_resp(200, {"type": "User", "login": "acme"})
    )
    mock_http.post = AsyncMock(
        return_value=_resp(
            201, {"html_url": "https://github.com/acme/dp-x", "full_name": "acme/dp-x"}
        )
    )
    mock_http.put = AsyncMock(return_value=_resp(200, {"names": [PLATFORM_TOPIC]}))
    with patch(
        "backend.infra.github_client.httpx.AsyncClient",
        return_value=_async_client_ctx(mock_http),
    ):
        await client.create_product_repo("dp-x", "desc")
    mock_http.put.assert_awaited_once()
    assert mock_http.put.await_args.args[0].endswith("/repos/acme/dp-x/topics")
    assert mock_http.put.await_args.kwargs["json"] == {"names": [PLATFORM_TOPIC]}


async def test_create_product_repo_survives_topic_tagging_failure(client):
    mock_http = AsyncMock()
    mock_http.get = AsyncMock(
        return_value=_resp(200, {"type": "User", "login": "acme"})
    )
    mock_http.post = AsyncMock(
        return_value=_resp(
            201, {"html_url": "https://github.com/acme/dp-x", "full_name": "acme/dp-x"}
        )
    )
    mock_http.put = AsyncMock(return_value=_resp(403, {"message": "no admin rights"}))
    with patch(
        "backend.infra.github_client.httpx.AsyncClient",
        return_value=_async_client_ctx(mock_http),
    ):
        result = await client.create_product_repo("dp-x", "desc")
    assert result["full_name"] == "acme/dp-x"


async def test_create_product_repo_raises_on_other_failure(client):
    mock_http = AsyncMock()
    mock_http.get = AsyncMock(
        return_value=_resp(200, {"type": "User", "login": "acme"})
    )
    mock_http.post = AsyncMock(return_value=_resp(500, {"message": "boom"}))
    with patch(
        "backend.infra.github_client.httpx.AsyncClient",
        return_value=_async_client_ctx(mock_http),
    ):
        with pytest.raises(RuntimeError):
            await client.create_product_repo("dp-x", "desc")


async def test_push_scaffold_puts_each_file(client):
    mock_http = AsyncMock()
    mock_http.get = AsyncMock(return_value=_resp(404))  # no existing sha
    mock_http.put = AsyncMock(return_value=_resp(201, {}))
    with patch(
        "backend.infra.github_client.httpx.AsyncClient",
        return_value=_async_client_ctx(mock_http),
    ):
        await client.push_scaffold(
            "acme/dp-x",
            {"README.md": "hello", "pipeline/.gitkeep": ""},
        )
    assert mock_http.put.await_count == 2
    urls = {call.args[0] for call in mock_http.put.await_args_list}
    assert any(u.endswith("/contents/README.md") for u in urls)
    assert any(u.endswith("/contents/pipeline/.gitkeep") for u in urls)


async def test_push_scaffold_raises_on_failure(client):
    mock_http = AsyncMock()
    mock_http.get = AsyncMock(return_value=_resp(404))
    mock_http.put = AsyncMock(return_value=_resp(500, {"message": "boom"}))
    with patch(
        "backend.infra.github_client.httpx.AsyncClient",
        return_value=_async_client_ctx(mock_http),
    ):
        with pytest.raises(RuntimeError):
            await client.push_scaffold("acme/dp-x", {"README.md": "hello"})


async def test_archive_repo_patches_archived_true(client):
    mock_http = AsyncMock()
    mock_http.patch = AsyncMock(return_value=_resp(200, {"archived": True}))
    with patch(
        "backend.infra.github_client.httpx.AsyncClient",
        return_value=_async_client_ctx(mock_http),
    ):
        await client.archive_repo("acme/dp-x")
    mock_http.patch.assert_awaited_once()
    url = mock_http.patch.await_args.args[0]
    assert url.endswith("/repos/acme/dp-x")
    body = mock_http.patch.await_args.kwargs["json"]
    assert body == {"archived": True}


async def test_archive_repo_raises_on_failure(client):
    mock_http = AsyncMock()
    mock_http.patch = AsyncMock(return_value=_resp(500, {"message": "boom"}))
    with patch(
        "backend.infra.github_client.httpx.AsyncClient",
        return_value=_async_client_ctx(mock_http),
    ):
        with pytest.raises(RuntimeError):
            await client.archive_repo("acme/dp-x")
