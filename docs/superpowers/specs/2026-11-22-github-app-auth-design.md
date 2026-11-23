# GitHub App Authentication Design

**Date:** 2026-11-22
**Status:** Implemented (rollout pending)

---

## Overview

The backend calls the GitHub API to push contracts to the central contracts repository and to create, scaffold, tag and archive one repository per data product. Until now it authenticated with a personal access token (`GH_CONTRACT_TOKEN` → Container App secret `github-token` → `GITHUB_TOKEN`). That token is long-lived, tied to a person, and its `repo` scope reaches every private repository of that person.

This change authenticates the backend as a **GitHub App** instead. The App's private key lives in **Azure Key Vault** and never leaves it: the backend, using its **managed identity**, asks Key Vault to sign the App JWT, exchanges the JWT for an **installation token valid for one hour**, and caches it. Nothing long-lived is stored in the app, in Container App secrets, or in GitHub secrets.

```
Container App (system-assigned managed identity, no secret)
  → Key Vault sign(RS256) with the App private key (key ops: sign only)
  → App JWT (iss = Client ID, 10 min)
  → POST /app/installations/{id}/access_tokens
  → installation token (1 h, cached in-process, renewed 5 min before expiry)
```

### Why not OIDC / federated credentials

GitHub Actions OIDC (used by `infra.yml`) works in the other direction: GitHub is the identity provider and Azure trusts it. GitHub does not accept an external identity (Entra ID, managed identity) to authenticate to its REST API, so a federated credential cannot be configured on the GitHub side. Signing the App JWT in Key Vault with the managed identity is the closest equivalent: the only credential is the platform-managed identity.

---

## Goals

- No long-lived GitHub credential in the backend, its configuration, or CI secrets.
- Credentials not tied to a person; actions show up as the App's bot.
- Least privilege: only the permissions the backend uses, only in the platform organization.
- Zero-downtime migration: the token keeps working until the App is fully configured.

## Non-goals

- Per-user GitHub authorization (OAuth). The platform acts as itself.
- Narrowing installation tokens per operation (one token with the App's permissions).
- Generating repositories from a template repository (possible follow-up).
- Migrating `scripts/migrate_contracts_to_odcs.py`, a one-off script that keeps using a token.

---

## GitHub App

| Setting | Value |
|---|---|
| Owner | Organization `data-mesh-platform-org` (installation tokens create repos via `POST /orgs/{org}/repos`) |
| Name | `dmplt` (commits appear as `dmplt[bot]`) |
| Repository permissions | Administration: read & write (create, archive, topics) · Contents: read & write (scaffold, contracts) · Metadata: read |
| Organization / account permissions | none |
| Webhook | inactive |
| OAuth / client secrets | not used; delete any client secret |
| Installation | `data-mesh-platform-org`, **All repositories** (so the App reaches the repositories it creates) |

Product repositories are created under the owner of `GITHUB_REPO`, so the contracts repository moves to the organization as part of the rollout.

---

## Components

### `backend/infra/github_auth.py` (new)

Both modes are `httpx.Auth` implementations, so `GitHubClient` is unaware of which one is active.

- `BearerTokenAuth(token)`: static token (legacy fallback).
- `GitHubAppAuth(client_id, installation_id, signer)`: builds the App JWT (`iat` backdated 60 s, `exp` +9 min, `iss` = Client ID), requests an installation token, caches it, and renews it once fewer than 5 minutes remain. An `asyncio.Lock` makes concurrent requests share one token request. On a `401` it drops the rejected token and retries the request once.
- `KeyVaultSigner(key_id)`: SHA-256 digest locally, RS256 signature in Key Vault via `CryptographyClient` + `DefaultAzureCredential` (managed identity in Azure, `az login` locally), run in a worker thread. A new `CryptographyClient` per signature resolves the latest key version, so a rotated key is picked up without a restart.
- `build_github_auth(...)`: App if all three App settings are set; otherwise the token; otherwise `None` (integration off). A partial App configuration is logged at `ERROR` and ignored.
- Credentials are attached only to `https://api.github.com`.

### `GitHubClient`

- Constructor is keyword-only: `GitHubClient(repo=..., token=...)` or `GitHubClient(repo=..., auth=...)`.
- All HTTP clients are built by `_http()`, with the auth and `follow_redirects=True`. GitHub answers `301`/`307` for transferred or renamed repositories, so `repo_url` values stored before the transfer to the organization keep working. httpx drops `Authorization` on cross-origin redirects.

### `backend/interface/dependencies.py`

`_github_auth()` is cached per process (`functools.cache`) so the installation token survives across requests; `get_github_client()` builds a `GitHubClient` around it.

---

## Configuration

| Variable | Where it comes from | Notes |
|---|---|---|
| `GITHUB_REPO` | repo variable `GH_CONTRACTS_REPO` (default `GuhBrando/dmplt_data_contract`) | Owner = where product repos are created |
| `GITHUB_APP_CLIENT_ID` | repo variable `GH_APP_CLIENT_ID` | Not a secret |
| `GITHUB_APP_INSTALLATION_ID` | repo variable `GH_APP_INSTALLATION_ID` | Not a secret |
| `GITHUB_APP_KEY_VAULT_KEY_ID` | repo variable `GH_APP_KEY_VAULT_KEY_ID` = `terraform output github_app_key_id` | Versionless key ID |
| `GITHUB_TOKEN` | secret `GH_CONTRACT_TOKEN` | Fallback, removed after cutover |

GitHub reserves the `GITHUB_` prefix for repository variables, hence the `GH_` names. While the App variables are empty, `cd.yml` deploys them empty and the backend keeps using the token.

---

## Infrastructure (platform stack)

- `azurerm_container_app.backend` gets a **system-assigned identity**.
- `azurerm_key_vault.main` (`dmplt-kv`): RBAC authorization, purge protection, 7-day soft-delete retention.
- `azurerm_role_assignment.backend_key_signer`: **Key Vault Crypto User** on the vault for the backend identity. Creating it needs Owner or User Access Administrator (see `infra/terraform/README.md`), so this apply is run by an operator, not CI.
- The key (`github-app`) is **not** a Terraform resource, so private key material never reaches Terraform state. Step 6 of `platform/grant-ci-permissions.sh` imports it (`az keyvault key import --ops sign`), requiring `GITHUB_APP_PEM` while the vault has no key and skipping once it does. It grants the operator **Key Vault Crypto Officer** only for the import (removed on exit, even on failure), retries while the new role propagates, and prints the key's SHA-256 fingerprint to compare with the one GitHub lists.
- **Drift reconciliation.** The first plan showed live settings Terraform would have reverted. Each is now either codified (matches Azure) or ignored (owned elsewhere), so the plan is clean:
  - Codified: `workload_profile_name = "Consumption"` and `transport = "http"` on the Container App, its `http-scaler` rule (10 concurrent requests), and the `Consumption` workload profile on `dmplt-cae`.
  - Ignored on the Container App, owned by `cd.yml`: container `image` and `env`, `secret`, `ingress.cors` (set from the `CORS_ORIGINS` secret). Also ignored: `ingress.traffic_weight` (single revision mode keeps no split) and the scale cooldown/polling (unset in Azure, so KEDA defaults apply).
  - Ignored on the Static Web App: `repository_url` / `repository_branch`, recorded by the deploy action on every release.

---

## Failure Modes

| Failure | Handling |
|---|---|
| Key Vault unreachable, or identity lacks the role | Token request raises; callers' existing warn-only handling applies (contract push logged, `repo_url` stays null and is retried lazily, sync returns 502). |
| GitHub rejects the JWT (wrong key, App deleted) | `RuntimeError` with GitHub's status and message; same handling as above. |
| Installation token revoked early | `401` → token dropped, request retried once with a fresh token. |
| Partial App configuration | `ERROR` log naming the missing variables; token fallback if present. |
| Repository transferred | Redirect followed. |

---

## Rollout

1. **GitHub (done).** Organization `data-mesh-platform-org`, App `dmplt` registered and installed on all repositories, private key downloaded.
2. **Release this code** with the App variables unset. Behaviour is unchanged (token), plus redirects are followed.
3. **Terraform apply** of `platform/` by an Owner (done 2026-11-22). Adding an identity in place leaves its `principal_id` unknown at plan time, so it takes two applies: first `-target` the Container App and the Key Vault (`dmplt-kv` created, identity added; Azure rolled a new revision with the same image and env), then a full apply (the role assignment). A final `plan -detailed-exitcode` must report no changes. If `dmplt-kv` was already created by hand, import it first: `terraform import 'module.backend_app.azurerm_key_vault.main' /subscriptions/<sub>/resourceGroups/dmplt-rg/providers/Microsoft.KeyVault/vaults/dmplt-kv`.
4. **Import the key** (Git Bash, from `infra/terraform/platform/`):
   `GITHUB_APP_PEM="<path-to>/<app>.<date>.private-key.pem" bash grant-ci-permissions.sh`.
   Compare the printed fingerprint with the one in the App's Key pairs tab, then delete the `.pem`.
5. **Transfer** `dmplt-data-contract` (renamed from `dmplt_data_contract`) and the existing product repositories (topic `data-mesh-platform`) to `data-mesh-platform-org` (repository Settings → Danger Zone → Transfer). Old URLs keep working through redirects.
6. **Repository variables** (not secrets: none of the values is sensitive) in `data-mesh-platform-org/data-mesh-plt` (Settings → Secrets and variables → Actions → Variables): `GH_CONTRACTS_REPO=data-mesh-platform-org/dmplt-data-contract`, `GH_APP_CLIENT_ID`, `GH_APP_INSTALLATION_ID`, `GH_APP_KEY_VAULT_KEY_ID` (printed by the script, also `terraform output github_app_key_id`).
7. **Release** (new tag). Check the backend log for `Obtained a GitHub App installation token`, create a test data product (repo appears in the organization, commits by `dmplt[bot]`), and run a contract sync.
8. **Cleanup** (follow-up change): drop `GITHUB_TOKEN` from `cd.yml`, remove the `github-token` Container App secret and the `GH_CONTRACT_TOKEN` GitHub secret, revoke the personal access token.

## Key Rotation

Generate a new key in the App (Credentials → Key pairs → New key) and import it under the same name, which creates a new version: `az keyvault key import --vault-name dmplt-kv --name github-app --pem-file <pem> --ops sign --protection software` (with a temporary Key Vault Crypto Officer role, as step 6 of the script does; the script itself skips once a key exists). Delete the local file, then delete the old key in GitHub. The backend signs with the latest version from its next JWT on; no restart or config change.

---

## Testing

- `tests/unit/infra/test_github_auth.py`: JWT produced through Key Vault semantics (a fake `CryptographyClient` signing the pre-hashed digest with a real RSA key) verifies with the public key via PyJWT; claims and lifetime; installation token request, caching, refresh margin, single request under concurrency, failure; auth flow header, one retry after `401`, no credentials to other hosts or plain HTTP; selection logic including partial configuration.
- `tests/unit/infra/test_github_client.py`: constructor needs exactly one credential; a `307` for a transferred repository is followed with credentials.
- `tests/conftest.py` blanks the App settings alongside `GITHUB_TOKEN`; `test_suite_isolation.py` asserts it.

## Decisions and Trade-offs

- **Key Vault signing over a PEM secret.** A PEM in a Container App secret would be simpler but is again a long-lived secret readable by anyone with access to the app's configuration. Signing in Key Vault costs one remote call per hour.
- **Organization over personal account.** Creating repositories with installation tokens is established for organizations; the installation is scoped to platform repositories only; teams and rulesets per domain become possible.
- **Client ID as JWT issuer.** GitHub now recommends it over the numeric App ID.
- **Fallback on partial configuration** rather than failing requests, consistent with the warn-only GitHub integration.
