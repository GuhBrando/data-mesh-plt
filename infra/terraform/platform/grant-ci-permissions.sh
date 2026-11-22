#!/usr/bin/env bash
# Grants the standing permissions that let GitHub Actions run the platform stack as
# the dmplt-devops service principal (OIDC), and lets human operators use the
# Azure AD-authenticated state backend.
#
# These are the grants Terraform cannot express in this stack:
#   - Storage Blob Data Contributor on the tfstate storage account must exist BEFORE
#     `terraform init` can read state (chicken-and-egg with the stack itself).
#   - dmplt-devops owning its OWN application/service principal is a dependency cycle
#     in HCL, and the standalone azuread_application_owner resource is incompatible
#     with the azuread_application resource this stack uses.
#   - The Microsoft Graph app role (Application.ReadWrite.OwnedBy) is admin consent,
#     which only a privileged human can grant.
#
# Grants (all least-privilege):
#   1. Signed-in user  -> Storage Blob Data Contributor on dmplttfstate
#   2. dmplt-devops SP -> Storage Blob Data Contributor on dmplttfstate
#   3. dmplt-devops SP -> Graph app role Application.ReadWrite.OwnedBy (admin consent)
#   4. dmplt-devops SP -> owner of the dmplt-admin and dmplt-devops apps and SPs
#   5. GitHub repository variables AZURE_CLIENT_ID / AZURE_TENANT_ID /
#      AZURE_SUBSCRIPTION_ID (consumed by .github/workflows/infra.yml)
#   6. GitHub App private key -> Key Vault dmplt-kv, key "github-app", restricted to
#      the sign operation. Kept out of Terraform so the key never reaches state. The
#      signed-in user gets "Key Vault Crypto Officer" only for the import.
#
# Run ONCE by an Owner + Global Administrator identity (az login). Idempotent: every
# grant is checked before it is made. If the platform stack has not been applied yet
# (dmplt-devops missing), only grant 1 is made — re-run after `terraform apply`.
#
# GITHUB_APP_PEM is REQUIRED while the key is not in the vault yet: the path to the
# .pem downloaded from the GitHub App (Settings > Developer settings > GitHub Apps >
# <app> > Credentials > Key pairs > New key). Once imported it is no longer needed;
# delete the local file.
#
# Prereqs: az CLI (logged in); gh CLI (logged in) for step 5; openssl (ships with Git
# Bash) to print the key fingerprint in step 6. Run in Git Bash on Windows.
#
# Usage:
#   GITHUB_APP_PEM="C:/Users/<you>/Downloads/<app>.<date>.private-key.pem" bash grant-ci-permissions.sh
#   bash grant-ci-permissions.sh                       # once the key is in the vault
#   AZURE_SUBSCRIPTION_ID=<id> AZURE_TENANT_ID=<id> bash grant-ci-permissions.sh  # override az session

set -euo pipefail

# Git Bash mangles arguments that start with "/" into Windows paths; --scope values
# like /subscriptions/... must reach az verbatim.
export MSYS_NO_PATHCONV=1

command -v az >/dev/null 2>&1 || { echo "ERROR: 'az' not found in PATH." >&2; exit 1; }

BLOB_ROLE="Storage Blob Data Contributor"
GRAPH_APP_ID="00000003-0000-0000-c000-000000000000" # Microsoft Graph (fixed, global)
GRAPH_ROLE="Application.ReadWrite.OwnedBy"

# --- resolve inputs (local env overrides; otherwise read from the az session) -------
SUB_ID="${AZURE_SUBSCRIPTION_ID:-$(az account show --query id -o tsv)}"
TENANT_ID="${AZURE_TENANT_ID:-$(az account show --query tenantId -o tsv)}"
TFSTATE_SCOPE="/subscriptions/$SUB_ID/resourceGroups/dmplt-tfstate-rg/providers/Microsoft.Storage/storageAccounts/dmplttfstate"
USER_OBJ_ID="$(az ad signed-in-user show --query id -o tsv)"
echo "==> Subscription $SUB_ID, signed-in user $USER_OBJ_ID"

# has_role <principal-object-id>
has_role() {
  [[ -n "$(az role assignment list --assignee "$1" --role "$BLOB_ROLE" --scope "$TFSTATE_SCOPE" --query "[0].id" -o tsv)" ]]
}

# grant_blob_role <principal-object-id> <principal-type> <label>
grant_blob_role() {
  if has_role "$1"; then
    echo "==> $3 already has '$BLOB_ROLE' on dmplttfstate. Nothing to do."
  else
    echo "==> Granting '$BLOB_ROLE' on dmplttfstate to $3 ..."
    az role assignment create --assignee-object-id "$1" --assignee-principal-type "$2" \
      --role "$BLOB_ROLE" --scope "$TFSTATE_SCOPE" >/dev/null
  fi
}

# --- 1. operator: blob access to the state backend (use_azuread_auth) ---------------
grant_blob_role "$USER_OBJ_ID" "User" "the signed-in user"

# --- locate dmplt-devops (created by this stack's identities module) ----------------
DEVOPS_SP_ID="$(az ad sp list --display-name dmplt-devops --query "[0].id" -o tsv)"
if [[ -z "$DEVOPS_SP_ID" ]]; then
  echo "==> dmplt-devops SP not found: the platform stack hasn't been applied yet."
  echo "    Operator grant done. Re-run this script after 'terraform apply' to grant CI."
  exit 0
fi
DEVOPS_APP_OBJ_ID="$(az ad app list --display-name dmplt-devops --query "[0].id" -o tsv)"
ADMIN_APP_OBJ_ID="$(az ad app list --display-name dmplt-admin --query "[0].id" -o tsv)"
ADMIN_SP_ID="$(az ad sp list --display-name dmplt-admin --query "[0].id" -o tsv)"
echo "==> dmplt-devops SP $DEVOPS_SP_ID, dmplt-admin SP $ADMIN_SP_ID"

# --- 2. CI: blob access to the state backend ----------------------------------------
grant_blob_role "$DEVOPS_SP_ID" "ServicePrincipal" "dmplt-devops"

# --- 3. CI: Graph Application.ReadWrite.OwnedBy (manage the apps it owns) -----------
GRAPH_SP_ID="$(az ad sp show --id "$GRAPH_APP_ID" --query id -o tsv)"
ROLE_ID="$(az ad sp show --id "$GRAPH_APP_ID" --query "appRoles[?value=='$GRAPH_ROLE'].id | [0]" -o tsv)"
ASSIGNED="$(az rest --method GET \
  --uri "https://graph.microsoft.com/v1.0/servicePrincipals/$DEVOPS_SP_ID/appRoleAssignments" \
  --query "value[?appRoleId=='$ROLE_ID'].id | [0]" -o tsv)"
if [[ -n "$ASSIGNED" ]]; then
  echo "==> dmplt-devops already has $GRAPH_ROLE. Nothing to do."
else
  echo "==> Granting Graph app role $GRAPH_ROLE to dmplt-devops (admin consent) ..."
  az rest --method POST \
    --uri "https://graph.microsoft.com/v1.0/servicePrincipals/$DEVOPS_SP_ID/appRoleAssignments" \
    --body "{\"principalId\":\"$DEVOPS_SP_ID\",\"resourceId\":\"$GRAPH_SP_ID\",\"appRoleId\":\"$ROLE_ID\"}" >/dev/null
fi

# --- 4. CI: ownership of both apps and SPs (OwnedBy only covers owned objects) ------
# ensure_owner <applications|servicePrincipals> <object-id> <label>
ensure_owner() {
  local existing
  existing="$(az rest --method GET --uri "https://graph.microsoft.com/v1.0/$1/$2/owners" \
    --query "value[?id=='$DEVOPS_SP_ID'].id | [0]" -o tsv)"
  if [[ -n "$existing" ]]; then
    echo "==> dmplt-devops already owns $3. Nothing to do."
  else
    echo "==> Adding dmplt-devops as owner of $3 ..."
    az rest --method POST --uri "https://graph.microsoft.com/v1.0/$1/$2/owners/\$ref" \
      --body "{\"@odata.id\":\"https://graph.microsoft.com/v1.0/directoryObjects/$DEVOPS_SP_ID\"}" >/dev/null
  fi
}

ensure_owner applications      "$ADMIN_APP_OBJ_ID"  "the dmplt-admin application"
ensure_owner applications      "$DEVOPS_APP_OBJ_ID" "its own application"
ensure_owner servicePrincipals "$ADMIN_SP_ID"       "the dmplt-admin service principal"
ensure_owner servicePrincipals "$DEVOPS_SP_ID"      "its own service principal"

# --- 5. GitHub repository variables (identifiers, not secrets) ----------------------
DEVOPS_CLIENT_ID="$(az ad sp show --id "$DEVOPS_SP_ID" --query appId -o tsv)"
if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
  echo "==> Setting GitHub repository variables (AZURE_CLIENT_ID / _TENANT_ID / _SUBSCRIPTION_ID) ..."
  gh variable set AZURE_CLIENT_ID --body "$DEVOPS_CLIENT_ID"
  gh variable set AZURE_TENANT_ID --body "$TENANT_ID"
  gh variable set AZURE_SUBSCRIPTION_ID --body "$SUB_ID"
else
  echo "WARNING: gh CLI missing or not authenticated — set the repository variables by hand:" >&2
  echo "  gh variable set AZURE_CLIENT_ID       --body $DEVOPS_CLIENT_ID" >&2
  echo "  gh variable set AZURE_TENANT_ID       --body $TENANT_ID" >&2
  echo "  gh variable set AZURE_SUBSCRIPTION_ID --body $SUB_ID" >&2
fi

echo "==> OK: CI (dmplt-devops) can now run the platform stack via OIDC."

# --- 6. GitHub App private key -> Key Vault (sign-only) -----------------------------
KV_NAME="dmplt-kv"
KEY_NAME="github-app"
KV_OFFICER_ROLE="Key Vault Crypto Officer"

KV_ID="$(az keyvault show --name "$KV_NAME" --query id -o tsv 2>/dev/null || true)"
if [[ -z "$KV_ID" ]]; then
  echo "ERROR: Key Vault $KV_NAME not found. Run 'terraform apply' in platform/ first." >&2
  exit 1
fi

# Management-plane read: works for an Owner without any Key Vault data-plane role.
KEY_URI="$(az rest --method GET \
  --uri "https://management.azure.com${KV_ID}/keys/${KEY_NAME}?api-version=2023-07-01" \
  --query properties.keyUri -o tsv 2>/dev/null || true)"

if [[ -n "$KEY_URI" ]]; then
  echo "==> GitHub App key already in $KV_NAME ($KEY_URI). Nothing to do."
else
  if [[ -z "${GITHUB_APP_PEM:-}" ]]; then
    echo "ERROR: the GitHub App key is not in $KV_NAME yet. Pass the .pem downloaded from" >&2
    echo "       the App (Credentials > Key pairs > New key):" >&2
    echo "  GITHUB_APP_PEM=\"C:/Users/<you>/Downloads/<app>.private-key.pem\" bash $0" >&2
    exit 1
  fi
  if [[ ! -f "$GITHUB_APP_PEM" ]]; then
    echo "ERROR: GITHUB_APP_PEM file not found: $GITHUB_APP_PEM" >&2
    exit 1
  fi
  # az is a Windows program under Git Bash and MSYS_NO_PATHCONV is on, so hand it a
  # Windows path (C:/...). cygpath only exists on Git Bash/Cygwin.
  PEM_PATH="$(cygpath -m "$GITHUB_APP_PEM" 2>/dev/null || printf '%s' "$GITHUB_APP_PEM")"

  # Temporary data-plane right to import. Removed on exit, even on failure, unless the
  # user already held it before this run.
  OFFICER_PREEXISTING="$(az role assignment list --assignee "$USER_OBJ_ID" \
    --role "$KV_OFFICER_ROLE" --scope "$KV_ID" --query "[0].id" -o tsv)"
  IMPORT_ERR="$(mktemp)"
  cleanup_key_import() {
    rm -f "$IMPORT_ERR"
    if [[ -z "$OFFICER_PREEXISTING" ]]; then
      echo "==> Removing the temporary '$KV_OFFICER_ROLE' role ..."
      az role assignment delete --assignee "$USER_OBJ_ID" --role "$KV_OFFICER_ROLE" \
        --scope "$KV_ID" >/dev/null 2>&1 || \
        echo "WARNING: remove '$KV_OFFICER_ROLE' on $KV_NAME from yourself by hand." >&2
    fi
  }
  trap cleanup_key_import EXIT
  if [[ -z "$OFFICER_PREEXISTING" ]]; then
    echo "==> Granting the signed-in user a temporary '$KV_OFFICER_ROLE' on $KV_NAME ..."
    az role assignment create --assignee-object-id "$USER_OBJ_ID" \
      --assignee-principal-type User --role "$KV_OFFICER_ROLE" --scope "$KV_ID" >/dev/null
  fi

  # A new role assignment takes a few minutes to reach the Key Vault data plane: retry
  # on Forbidden only; any other error (e.g. a file that is not an RSA key) is final.
  echo "==> Importing the GitHub App key into $KV_NAME as '$KEY_NAME' (ops: sign) ..."
  for attempt in $(seq 1 12); do
    if az keyvault key import --vault-name "$KV_NAME" --name "$KEY_NAME" \
         --pem-file "$PEM_PATH" --ops sign --protection software \
         >/dev/null 2>"$IMPORT_ERR"; then
      break
    fi
    if grep -qi "forbidden" "$IMPORT_ERR" && [[ "$attempt" -lt 12 ]]; then
      echo "    role not effective yet (attempt $attempt/12), retrying in 20s ..."
      sleep 20
      continue
    fi
    cat "$IMPORT_ERR" >&2
    echo "ERROR: key import failed." >&2
    exit 1
  done

  KEY_URI="$(az keyvault key show --vault-name "$KV_NAME" --name "$KEY_NAME" \
    --query key.kid -o tsv)"
  echo "==> Imported $KEY_URI"
  if command -v openssl >/dev/null 2>&1; then
    # Same fingerprint GitHub lists next to the key in the App's Key pairs tab.
    # Informational only: never abort after a successful import (set -e/pipefail).
    FINGERPRINT="$(openssl rsa -in "$GITHUB_APP_PEM" -pubout -outform DER 2>/dev/null \
      | openssl sha256 -binary | openssl base64 || true)"
    if [[ -n "$FINGERPRINT" ]]; then
      echo "    Fingerprint SHA256:$FINGERPRINT — must match the key shown on GitHub."
    fi
  fi
  echo ""
  echo "IMPORTANT: the key now lives only in Key Vault. Delete the local file:"
  echo "  rm \"$GITHUB_APP_PEM\""
  echo ""
fi

echo "==> OK: backend setting GITHUB_APP_KEY_VAULT_KEY_ID=https://${KV_NAME}.vault.azure.net/keys/${KEY_NAME}"
echo "    (repository variable GH_APP_KEY_VAULT_KEY_ID; see"
echo "    docs/superpowers/specs/2026-11-22-github-app-auth-design.md for the cutover)"
