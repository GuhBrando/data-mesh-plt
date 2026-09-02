# MCP Catalog Server Design

**Date:** 2026-08-09
**Status:** Draft
**Protocol revision:** MCP `2026-07-28`

---

## Overview

The platform's catalog — data contracts, tiers, domains, and data products — is reachable
only through the web UI and the REST API today. Any agent that wants to answer "which
contracts exist in the marketing domain", "what does the exposicao-credito contract
guarantee", or "what tier is this product and what does that require" has no way in.

This change adds a **read-only MCP server** that exposes the catalog as tools, resources,
and prompts, so that MCP-compatible clients (Claude Desktop, Claude Code, Cursor, IDE
agents) can query it directly.

The server is a **thin translation layer**: it receives `tools/call`, calls the existing
REST API with the caller's own JWT, and returns the result. It adds no business logic, no
database access, and no write path. Every RBAC rule the platform already enforces —
`require_roles`, `is_domain_member`, the stakeholder restriction on contract detail —
continues to apply unchanged, because the server is just another authenticated API client.

Phase 1 ships STDIO only. The tool layer is written transport-agnostic so that mounting a
Streamable HTTP endpoint later is an additive change, not a rewrite.

---

## Goals

- Expose catalog discovery to MCP clients without duplicating authorization logic.
- Ship with zero new infrastructure and zero new cost.
- Keep all MCP SDK coupling inside a single module, so the beta SDK can be swapped or
  upgraded without touching tool logic.
- Demonstrate all three MCP primitives correctly: tools (model-controlled), resources
  (application-controlled), prompts (user-controlled).
- Leave a clean seam for a Streamable HTTP transport in phase 2.

## Non-goals

- **Any write path.** No `create_contract`, no `update_contract`, no PR creation. Explicitly
  deferred; see Decisions.
- **Lineage tools.** `input_ports`, `output_ports`, and `consumers` do not exist in the
  schema (see Schema Constraints below). Nothing to expose yet.
- **Streamable HTTP transport and OAuth 2.1.** Phase 2.
- **Server-side search/filter query parameters on the REST API.** Phase 1 filters
  client-side; see Tool Surface.
- **A hosted, multi-tenant MCP endpoint.** Phase 1 is one process per person.
- **Changing the existing REST API contract.** The MCP server is purely additive.

---

## Schema Constraints

The README describes a richer model than the database currently implements. The tool
surface is scoped to what actually exists:

| README concept | Schema today | Consequence |
|---|---|---|
| `data_contracts` | Exists — `title`, `version`, `owner`, `domain_id`, `tier`, `status`, `models`, `servicelevels` | Fully exposable |
| `domains` | Exists, with membership | Fully exposable |
| `data_products` | Exists — but a single `data_contracts_id` FK, not a port collection | Product→contract is 1:1; reverse lookup is a client-side filter |
| `input_ports` / `output_ports` | **Absent** | No lineage tool |
| `consumers` | **Absent** | No consumer-impact tool |
| `contract_versions` | **Absent** (single `version` string on the row) | No version-history tool |
| `approvals`, `quality_violations` | **Absent** | Not exposed |

When those tables land, the tool surface extends additively — each new tool is a new entry
in the registry, with no change to transport, auth, or existing tools.

---

## Protocol Baseline (`2026-07-28`)

This revision is stateless, which materially simplifies the server:

- **No `initialize` handshake.** Protocol version, client capabilities, and client identity
  arrive in `_meta` on every request. The server holds no per-connection state.
- **No `Mcp-Session-Id`.** Nothing to store, nothing to route stickily. This is what makes
  the phase-2 HTTP mount cheap: any request can land on any container instance.
- **`server/discover` is mandatory** — advertises supported protocol versions, capabilities,
  and identity.
- **Every result carries `resultType`.** All tools here return `"complete"`; the
  `"input_required"` (MRTR) path is unused because no tool needs to ask the user anything.
- **List results carry `ttlMs` and `cacheScope`.** `tools/list`, `resources/list`, and
  `prompts/list` set `ttlMs` so clients cache instead of polling.
- **Tools must be returned in deterministic order** — the tool registry is an ordered
  structure, not a dict comprehension over an unordered source.
- **Logging feature is deprecated.** The server logs to `stderr`, per the spec's own
  migration guidance for STDIO.

**SDK maturity risk:** official SDKs for `2026-07-28` are in beta at the time of writing.
This design confines all SDK-specific code to `backend/mcp/server.py`; tool logic lives in
plain functions that the SDK adapts. An SDK breaking change touches one file.

---

## Architecture

```
┌──────────────────┐
│  MCP client      │   Claude Desktop / Claude Code / Cursor
└────────┬─────────┘
         │  JSON-RPC over stdin/stdout
         ▼
┌──────────────────────────────────────────────────────┐
│  backend/mcp/server.py         ← ALL SDK coupling    │
│    · server/discover, tools/list, tools/call         │
│    · resources/*, prompts/*                          │
│    · logs to stderr, never stdout                    │
├──────────────────────────────────────────────────────┤
│  backend/mcp/tools.py          ← pure async funcs    │
│    · no SDK imports, no transport knowledge          │
│    · (client, **kwargs) -> dict                      │
├──────────────────────────────────────────────────────┤
│  backend/mcp/client.py         ← CatalogClient        │
│    · httpx against the platform REST API             │
│    · Bearer JWT, refresh-on-401                      │
└────────┬─────────────────────────────────────────────┘
         │  HTTPS
         ▼
┌──────────────────────────────────────────────────────┐
│  Platform REST API  /api/v1/...                      │
│    existing RBAC applies unchanged                   │
└──────────────────────────────────────────────────────┘
```

Three layers, one responsibility each. `descriptions.py`, `prompts.py`, and `reference/`
are content files supporting the adapter layer — they hold text, not logic.

**`client.py` — `CatalogClient`.** A thin `httpx.AsyncClient` wrapper over the read
endpoints. Mirrors the shape of `backend/infra/github_client.py`: explicit methods, an
internal `_raise_for_status`, no ORM, no caching. Methods:

```python
async def list_contracts(self) -> list[dict]
async def get_contract(self, contract_id: str) -> dict
async def get_contract_yaml(self, contract_id: str) -> str
async def list_products(self) -> list[dict]
async def get_product(self, product_id: str) -> dict
async def list_domains(self) -> list[dict]
```

**`tools.py` — tool implementations.** Plain async functions taking a `CatalogClient` plus
keyword arguments, returning JSON-serializable dicts. No MCP imports. This is what makes
the layer transport-agnostic and trivially unit-testable with a stubbed client.

**`server.py` — MCP adapter.** Registers the tool/resource/prompt surface with the SDK,
maps exceptions to JSON-RPC errors, wires `stderr` logging, and runs the STDIO loop.

In phase 2, a `backend/interface/routers/mcp.py` mounts the *same* `tools.py` behind a
Streamable HTTP route, swapping `CatalogClient` for an in-process adapter that calls the
use cases directly. `tools.py` does not change.

---

## Tool Surface

Six tools, ordered deterministically as listed.

| Tool | Input | Backing call | Notes |
|---|---|---|---|
| `search_contracts` | `domain?`, `tier?`, `status?`, `query?` | `GET /api/v1/data-contracts` | Filters client-side; `query` matches `title` and `owner`, case-insensitive |
| `get_contract` | `contract_id` | `GET /api/v1/data-contracts/{id}` | Returns structured JSON incl. `models`, `servicelevels` |
| `get_contract_yaml` | `contract_id` | `GET /api/v1/data-contracts/{id}/yaml` | ODCS YAML as assembled by `yaml_builder.assemble_yaml` |
| `list_domains` | — | `GET /api/v1/domains` | Includes members; useful for ownership questions |
| `search_products` | `query?` | `GET /api/v1/data-products` | Filters client-side on `name` and `description` |
| `find_contract_implementations` | `contract_id` | `GET /api/v1/data-products` | Products whose `data_contracts_id` matches; the reverse lookup the API does not offer |

### Client-side filtering

The list endpoints accept no query parameters. Rather than change the REST API in phase 1,
`search_contracts` and `search_products` fetch the full list and filter in the tool.

This is a deliberate, bounded trade-off. It is correct and zero-touch at current catalog
size (tens to low hundreds of contracts). It becomes wrong somewhere in the low thousands,
where every search transfers the whole catalog. **Trigger to revisit:** when
`GET /api/v1/data-contracts` p95 latency exceeds ~500 ms, add `domain`, `tier`, and
`status` query parameters to the endpoint and push the filter down. The tool signatures do
not change when that happens.

### Tool descriptions

Descriptions are the primary control over whether the model calls a tool correctly, so each
one states **when to call it**, not merely what it returns. Example:

```
search_contracts — Search the data mesh catalog for data contracts. Call this when the
user asks what data exists, what a domain publishes, or which contracts match a tier or
status. Returns contract summaries (id, title, version, owner, domain, tier, status).
To read the full schema, quality rules, and SLAs of a specific contract, follow up with
get_contract or get_contract_yaml using the returned id.
```

Tier semantics are **not** repeated in tool descriptions — that knowledge lives in a
resource (below), so it is stated once.

---

## Resources

Resources are application-controlled: the host decides what to place in context.

| URI | Content | `cacheScope` |
|---|---|---|
| `datamesh://reference/tiers` | The tier definitions and classification rules from the README — what Tier 1–4 require in schema rigor, quality rules, SLA, deprecation window, and approvals | `public` |
| `datamesh://reference/evolution-policy` | The breaking / non-breaking / silent-semantic-change policy and its versioning rules | `public` |
| `datamesh://contract/{id}/yaml` | Resource **template** — the ODCS YAML for one contract | `private` |

The two reference resources are static text shipped with the server, generated from the
README at build time is **not** proposed — they are maintained as literal files under
`backend/mcp/reference/`, and a unit test asserts the tier table matches the README's, so
drift is caught in CI rather than discovered by an agent giving wrong advice.

`datamesh://contract/{id}/yaml` intentionally duplicates `get_contract_yaml`. That is the
primitive distinction working as intended: the tool is for when the *model* decides it
needs the YAML mid-reasoning; the resource is for when the *user* attaches a contract to
the conversation up front.

---

## Prompts

User-invoked templates. Both are read-only — they produce text for the user, and never
write to the platform.

| Prompt | Arguments | Purpose |
|---|---|---|
| `review_contract` | `contract_id` | Fetches the contract and the tier reference, then asks the model to audit it against its tier's requirements and flag gaps (missing quality rules, absent SLA fields, under-specified semantics) |
| `draft_contract` | `domain`, `tier` | Walks the user through drafting an ODCS contract at the required rigor for that tier, emitting YAML the user can paste into a PR themselves |

`draft_contract` is the deliberate compromise on the write path: the agent produces the
artifact, the human carries it through the existing `CODEOWNERS` review. No write tool is
needed to get most of the authoring value.

---

## Authentication

STDIO runs as the invoking user, so identity is already resolved by the operating system.
The server carries the user's own credentials and never elevates.

**Token handling:**

- `PLATFORM_TOKEN` — an access token (HS256 JWT, `sub` = user id), sent as
  `Authorization: Bearer`.
- `PLATFORM_REFRESH_TOKEN` — optional. On a `401` the client `POST`s to
  `/api/v1/auth/refresh` once, replaces the in-memory access token, and retries the
  original request exactly once. A second `401` surfaces as a tool error telling the user
  to re-authenticate.

Access tokens expire per `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`, so a long-lived agent session
without the refresh token will start failing mid-conversation. The refresh token is
optional but strongly recommended in the client config.

**Credentials are never logged.** The `stderr` logger redacts `Authorization` headers and
never logs response bodies from `/auth/*`.

**No new RBAC.** The server issues ordinary authenticated requests. A `DATA_CONSUMER` gets
consumer-level answers; a `PLATFORM_ADMIN` gets admin-level answers. There is no service
account and no shared token — that would create exactly the RBAC bypass this design exists
to avoid.

---

## Pre-existing Access-Control Finding

`GET /api/v1/data-contracts/{contract_id}` enforces a stakeholder restriction —
a `DATA_CONSUMER` who is not a registered stakeholder receives `403`
(`data_contract.py:163-166`).

`GET /api/v1/data-contracts/{contract_id}/yaml` enforces **no such check** — it depends only
on `get_current_user` (`data_contract.py:144-153`). Any authenticated user, including a
non-stakeholder `DATA_CONSUMER`, can read the full ODCS YAML of any contract, which is a
superset of what the restricted JSON endpoint returns.

This gap exists today and is independent of MCP. It matters here because `get_contract_yaml`
would turn a hard-to-hit inconsistency into a tool an agent reaches for routinely.

**This design does not fix it** — that is a separate change to the REST API with its own
test and review. It is recorded here so the decision is explicit rather than accidental.
Two options were considered:

1. Apply the stakeholder check to the YAML endpoint, matching the JSON endpoint. Consistent,
   but arguably contradicts the README's "contracts are public by design" stance.
2. Remove the stakeholder check from the JSON endpoint, making contract *reads* uniformly
   open to authenticated users and reserving stakeholder status for notification routing.

**Resolved in PR #25** — option 1 was taken: the YAML endpoint now enforces the same
stakeholder check, and the rule was extracted into a shared helper so the two
representations cannot drift apart again. Option 2 broadens access and remains available
as a separate, deliberate governance change if the "public by design" reading wins.

---

## Transport

### Phase 1 — STDIO

The client launches the server as a child process:

```json
{
  "mcpServers": {
    "data-mesh": {
      "command": "uv",
      "args": ["run", "python", "-m", "backend.mcp.server"],
      "cwd": "/path/to/data_mesh_plt",
      "env": {
        "PLATFORM_API_URL": "https://<app>.azurecontainerapps.io",
        "PLATFORM_TOKEN": "<access token>",
        "PLATFORM_REFRESH_TOKEN": "<refresh token>"
      }
    }
  }
}
```

JSON-RPC messages are newline-delimited on `stdin`/`stdout`. **Nothing may write to
`stdout` except protocol frames** — a stray `print()` corrupts the stream and the client
disconnects without a usable error. The server configures `logging` to `stderr` at import
time, before any other import that might attach a default handler.

### Phase 2 — Streamable HTTP (deferred)

Mounted at `POST /mcp` on the existing FastAPI app, reusing the running container. The
stateless protocol means no sticky routing and no shared session store.

The open work in phase 2 is authorization, not transport: MCP specifies the server as an
OAuth 2.1 Resource Server, while the platform currently issues its own HS256 JWTs. Either
the existing Bearer token is accepted directly (pragmatic, non-conformant) or an OAuth
layer is introduced (conformant, significantly more work). That decision is deferred until
there is a concrete consumer that STDIO cannot serve.

---

## Error Handling

| Condition | Behavior |
|---|---|
| Missing `PLATFORM_API_URL` or `PLATFORM_TOKEN` | Fail fast at startup with a message on `stderr`; do not start the loop |
| `401` from the API | Refresh once if `PLATFORM_REFRESH_TOKEN` is set, retry once; otherwise return a tool error instructing the user to re-authenticate |
| `403` from the API | Return a tool error stating the caller lacks permission — do **not** retry, and do not reveal whether the resource exists |
| `404` from the API | Return a tool error stating the resource was not found |
| `5xx` / network / timeout | Return a tool error naming the failure; the model may retry |
| Malformed tool arguments | Rejected by the tool's `inputSchema` before the function runs |

Tool errors are returned as tool results flagged as errors — not as JSON-RPC protocol
errors — so the model can read them and adapt. Protocol-level errors are reserved for
malformed requests and unsupported protocol versions.

Unlike the GitHub integration, failures here are **not** warn-only. There is no partial
success worth preserving: if the catalog cannot be reached, the honest answer is an error,
not an empty list that the model will interpret as "no contracts exist".

---

## Configuration

| Variable | Required | Purpose |
|---|---|---|
| `PLATFORM_API_URL` | Yes | Base URL of the platform API, without the `/api/v1` suffix |
| `PLATFORM_TOKEN` | Yes | Access token used as `Authorization: Bearer` |
| `PLATFORM_REFRESH_TOKEN` | No | Enables transparent refresh on `401` |
| `PLATFORM_TIMEOUT_SECONDS` | No | `httpx` timeout, default `15.0` |

These are read from the process environment supplied by the MCP client config, **not** from
`backend/infra/config.py` — the MCP server is a client of the platform, not an instance of
it, and must not inherit database or JWT-secret configuration.

New dependency: the official MCP Python SDK, pinned to an exact beta version in
`pyproject.toml` under a new `mcp` optional-dependency group, so the core platform install
is unaffected. `httpx` is already a direct dependency.

---

## Testing

**Unit — `CatalogClient`** (mock `httpx.AsyncClient`, matching the existing
`test_github_client.py` pattern):

- Each method issues the expected request with the `Authorization` header set.
- `401` with a refresh token configured triggers exactly one `POST /auth/refresh`, then one
  retry of the original request.
- `401` without a refresh token raises without attempting a refresh.
- A second consecutive `401` after refresh raises rather than looping.
- `403`, `404`, and `5xx` raise distinguishable errors.

**Unit — tools** (stubbed `CatalogClient`, no HTTP):

- `search_contracts` with no filters returns every contract.
- `search_contracts` filters correctly and independently by `domain`, `tier`, and `status`.
- `query` matches `title` and `owner` case-insensitively and does not match unrelated fields.
- `find_contract_implementations` returns only products whose `data_contracts_id` matches,
  and an empty list — not an error — when there are none.
- `get_contract_yaml` returns the body verbatim, without re-parsing the YAML.
- Every tool propagates client errors rather than swallowing them into empty results.

**Unit — server registration:**

- `tools/list` returns all six tools in a stable order across repeated calls.
- Every tool has a non-empty description and a valid `inputSchema`.
- Every advertised resource URI resolves.
- `ttlMs` and `cacheScope` are present on list results.

**Unit — reference drift:**

- The tier table in `backend/mcp/reference/tiers.md` matches the tier table in `README.md`.

**Unit — logging hygiene:**

- Importing `backend.mcp.server` attaches no handler that writes to `stdout`.
- The redacting formatter removes `Authorization` header values.

Integration tests against a live API are out of scope, consistent with the existing
mocked-`httpx` convention in this repo.

---

## Component Touch List

```
backend/
└── mcp/                              # new package
    ├── __init__.py
    ├── server.py                     # MCP SDK adapter, STDIO entrypoint, stderr logging
    ├── tools.py                      # 6 pure async tool functions
    ├── client.py                     # CatalogClient (httpx)
    ├── descriptions.py               # tool/resource/prompt text, kept out of logic
    ├── prompts.py                    # review_contract, draft_contract templates
    └── reference/
        ├── tiers.md                  # datamesh://reference/tiers
        └── evolution-policy.md       # datamesh://reference/evolution-policy

tests/unit/mcp/                       # new
├── test_catalog_client.py
├── test_tools.py
├── test_server_registration.py
└── test_reference_drift.py

pyproject.toml                        # + [project.optional-dependencies] mcp
docs/
└── mcp-server.md                     # setup guide: token, client config, troubleshooting

# Unchanged: all routers, use_cases, repositories, entities, migrations, frontend.
```

No database migration. No change to any existing module.

---

## Decisions and Trade-offs

**Why call the REST API instead of the use cases directly?**
The STDIO server runs on a developer laptop; the Postgres instance is in Azure and not
reachable from there. Going through the API is the only option that works for phase 1 — and
it has the better property anyway: the server inherits every authorization rule for free
instead of reimplementing `is_domain_member` and the stakeholder check against the database.
The cost is one extra network hop per tool call, which is irrelevant at agent latency.

**Why a three-module split instead of one file?**
The transport-agnostic tool layer is the entire point of the phased approach. If `tools.py`
imported the MCP SDK or knew about HTTP, phase 2 would be a rewrite. Keeping the SDK in one
adapter file also contains the beta-SDK risk to a single blast radius.

**Why read-only?**
A write tool means an agent can mutate a Tier 1 contract. The tier system exists precisely
to make that require multi-stakeholder approval. `draft_contract` captures most of the
authoring value by producing YAML the human carries through the existing `CODEOWNERS` flow,
with no new bypass of governance.

**Why STDIO before HTTP?**
STDIO needs no deployment, no container, no TLS, and no new authorization design — identity
arrives already resolved. HTTP requires solving the OAuth-versus-existing-JWT question,
which is real work with no consumer demanding it yet. Building the tool layer first means
that work is additive when it arrives.

**Why client-side filtering?**
Adding query parameters to `GET /data-contracts` is a change to a public API endpoint with
its own tests and frontend implications, in service of a tool that does not exist yet.
Filtering in the tool is correct at current scale and reversible without changing the tool
signature. The revisit trigger is written down above so the decision is not silently
forgotten.

**Why tier knowledge as a resource rather than in tool descriptions?**
Tool descriptions ride in the context on every request that lists tools. Tier rules are
several hundred tokens and needed only when a tier question actually comes up. A resource
is loaded on demand and stated exactly once, which also means one place to keep in sync
with the README.

**Why not warn-only failures, when the GitHub client is warn-only?**
Different failure semantics. A failed GitHub push leaves the platform correct and retries
later. A failed catalog read returned as an empty list would make the model confidently
state that no contracts exist. Silence is a worse answer than an error here.

**Why a drift test against the README?**
The reference resources restate content that lives in the README. Duplication is acceptable
because the agent-facing copy needs to be a standalone document, but undetected drift means
an agent giving governance advice from a stale tier table. A cheap test converts a silent
correctness problem into a CI failure.

---

## Open Questions

1. **Transport confirmation.** This design assumes the decoupled-tool-layer, STDIO-first
   option. That decision was raised but not confirmed. If the intent is instead to expose a
   single organization-wide HTTP endpoint from day one, the auth section grows substantially
   and phase 1 and 2 collapse into one larger piece of work.

2. ~~**Stakeholder check on the YAML endpoint.**~~ **Resolved** — PR #25 tightened the
   YAML endpoint to match the JSON one. `get_contract_yaml` inherits the corrected rule and
   needs no special handling.

3. **MCP SDK version.** Which beta of the Python SDK to pin, and whether to wait for a
   stable `2026-07-28` release before merging.
