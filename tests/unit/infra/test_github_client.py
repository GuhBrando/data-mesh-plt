import base64
import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from backend.infra.github_client import (
    PLATFORM_TOPIC,
    ContractFile,
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


@pytest.fixture
def http():
    mock_http = AsyncMock()
    with patch(
        "backend.infra.github_client.httpx.AsyncClient",
        return_value=_async_client_ctx(mock_http),
    ):
        yield mock_http


def _tree(*items: tuple[str, str]) -> MagicMock:
    return _resp(200, {"tree": [
        {"path": p, "type": "blob", "sha": s, "url": f"https://api.test/blobs/{s}"}
        for p, s in items
    ]})


def _blob(text: str) -> MagicMock:
    return _resp(200, {"content": base64.b64encode(text.encode()).decode()})


async def test_read_contract_files_returns_path_content_and_sha(client, http):
    http.get.side_effect = [
        _tree(("contracts/a/x.yaml", "sha-x"), ("README.md", "sha-r")),
        _blob("id: 1\n"),
    ]
    assert await client.read_contract_files() == [
        ContractFile("contracts/a/x.yaml", "id: 1\n", "sha-x")
    ]


async def test_read_contract_files_raises_on_tree_failure(client, http):
    http.get.return_value = _resp(401, {"message": "Bad credentials"})
    with pytest.raises(RuntimeError, match="401"):
        await client.read_contract_files()


async def test_read_contract_files_raises_on_blob_failure(client, http):
    http.get.side_effect = [
        _tree(("contracts/a/x.yaml", "s")), _resp(403, {"message": "rate limit"}),
    ]
    with pytest.raises(RuntimeError, match="403"):
        await client.read_contract_files()


async def test_list_all_yaml_contents_raises_on_failure(client, http):
    # A dead token or a renamed repository must not look like an empty sync.
    http.get.return_value = _resp(401, {"message": "Bad credentials"})
    with pytest.raises(RuntimeError, match="401"):
        await client.list_all_yaml_contents()


async def test_list_all_yaml_contents_returns_path_and_content(client, http):
    http.get.side_effect = [_tree(("contracts/a/x.yaml", "s")), _blob("id: 1\n")]
    assert await client.list_all_yaml_contents() == [("contracts/a/x.yaml", "id: 1\n")]


async def test_read_contract_files_refuses_a_truncated_tree(client, http):
    tree = _tree(("contracts/a/x.yaml", "s"))
    tree.json.return_value = {**tree.json.return_value, "truncated": True}
    http.get.return_value = tree
    with pytest.raises(RuntimeError, match="truncated"):
        await client.read_contract_files()


async def test_read_contract_files_names_a_file_that_is_not_utf8(client, http):
    latin1 = _resp(200, {"content": base64.b64encode("ação".encode("latin-1")).decode()})
    http.get.side_effect = [_tree(("contracts/a/x.yaml", "s")), latin1]
    with pytest.raises(RuntimeError, match="contracts/a/x.yaml is not a readable UTF-8"):
        await client.read_contract_files()


async def test_read_contract_files_refuses_an_item_without_sha(client, http):
    http.get.return_value = _resp(200, {"tree": [
        {"path": "contracts/a/x.yaml", "type": "blob", "url": "u"}]})
    with pytest.raises(RuntimeError, match="without a sha"):
        await client.read_contract_files()


async def test_read_contract_files_keeps_the_tree_order(client, http):
    http.get.side_effect = [
        _tree(("contracts/a/x.yaml", "sx"), ("contracts/b/y.yaml", "sy")),
        _blob("x\n"), _blob("y\n"),
    ]
    assert [f.path for f in await client.read_contract_files()] == [
        "contracts/a/x.yaml", "contracts/b/y.yaml"]


async def test_push_with_expected_sha_sends_it_without_a_lookup(client, http):
    http.put.return_value = _resp(200, {})
    await client.push("contracts/a/x.yaml", "body", "msg", expected_sha="abc")
    http.get.assert_not_awaited()
    assert http.put.await_args.kwargs["json"]["sha"] == "abc"


async def test_push_with_empty_expected_sha_does_not_look_it_up(client, http):
    # An empty sha must not fall back to last-writer-wins.
    http.put.return_value = _resp(200, {})
    await client.push("contracts/a/x.yaml", "body", "msg", expected_sha="")
    http.get.assert_not_awaited()


async def test_push_without_expected_sha_looks_the_sha_up(client, http):
    http.get.return_value = _resp(200, {"sha": "current"})
    http.put.return_value = _resp(200, {})
    await client.push("contracts/a/x.yaml", "body", "msg")
    assert http.put.await_args.kwargs["json"]["sha"] == "current"
