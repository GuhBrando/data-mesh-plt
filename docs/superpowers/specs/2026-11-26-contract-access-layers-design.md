# Contract Access Layers: Readers, Approval and Owner

**Date:** 2026-11-26
**Status:** Approved by the owner (2026-11-26)

## Why

A user who belongs to a domain could not open that domain's contracts. Their
platform role is `DATA_CONSUMER`, and the code lets a consumer read a contract
only when they are a stakeholder of it, on **every** contract, published or not.
There is no screen to add stakeholders, so the only way out was the Swagger UI.

The owner wants the model that data mesh platforms use, in three layers:

1. **Readers (consumers):** everyone reads the published contracts. The catalog
   is the shop window: a consumer judges owner, schema, quality and SLA before
   using a product (README, step 8: "outros times veem o produto no catálogo —
   podem ler o contrato").
2. **Approval:** only stewards of the contract's domain propose changes; a
   contract is published only when the domain's owner approves it.
3. **Owner:** the domain's Data Owner approves or sends back, deprecates, retires
   and deletes.

This is also what `docs/superpowers/specs/2026-04-28-rbac-design.md` already
specified (published contracts readable by all; drafts by the domain and by
stakeholders; Steward edits, Owner approves). The code drifted from it:

| Rule | RBAC spec | Code today |
|---|---|---|
| Consumer reads a published contract | yes | only as a stakeholder |
| Consumer reads a draft | only as a stakeholder | only as a stakeholder |
| `team`, `support`, `servers` in the list | visible | emptied for consumers who are not stakeholders |
| Owner approves / rejects | yes | no: approval is a `PUT`, which only Steward/Admin may call |
| Steward publishes on their own | no | yes: the form's status select accepts `active` |

## Goals

- Every signed-in user reads every published contract in full (JSON, YAML,
  versions, version YAML, usage).
- Drafts are read only by the contract's domain (Owner and Steward members),
  by Platform Admins and by invited stakeholders.
- Status changes follow a transition table enforced by the backend. The form no
  longer sets the status.
- The contract page shows each user only the actions they may take, and explains
  the state of the contract ("Draft: only Finance and invited reviewers can see
  it", "Awaiting the owner's review").
- A **Stakeholders** panel lets the Steward invite people to review a draft.

## Non-goals (follow-ups)

- **Approval of changes to a published contract** (pending versions). See
  "Decision: changes to a published contract" below.
- **Tiered, multi-level approval** (README step 6: Tier 1 needs domain owners,
  governance and compliance). ODCS models it in `roles[].firstLevelApprovers` /
  `secondLevelApprovers`. One approver (the domain's Owner) for now.
- **Access to the data itself** (request access to an output port, approved by
  the owner, applied as a `GRANT` in Unity Catalog).
- Comments on "Request changes", notifications, and the visibility of drafts in
  the central GitHub contracts repository (pushed on every save today).
- Moving a contract to another domain: today's check covers only the current
  domain. Unchanged.

## Anti-goals

- A consumer must **never lose access** to a contract they already read. No
  transition goes from a published status back to `draft` or `in_review`.
- No button that answers `403`. If the user cannot act, the action is not shown.
- No second copy of a rule. Who may read and who may move a status is decided in
  one backend module; the frontend renders what the backend says.

## Statuses

Published: `active`, `deprecated`, `retired`. Unpublished: `draft`,
`in_review`. Unchanged from today's `CONTRACT_STATUSES`.

## Layer 1: Readers

`can_read(contract, user)`:

1. Published: everyone.
2. Platform Admin: everything.
3. Data Owner or Data Steward who is a member of the contract's domain
   (`catalog.domain_members`, same check as create/update/delete today).
4. Stakeholder of the contract (`catalog.contract_stakeholders`).
5. Otherwise no.

Applied to:

- `GET /data-contracts`: drafts the user cannot read are **left out** of the list
  (today they appear with sections emptied). `_RESTRICTED_SECTIONS` and the
  section stripping go away. Bulk inputs, no N+1: the user's domain ids and the
  user's stakeholder contract ids, one query each.
- `GET /data-contracts/{id}`, `/yaml`, `/versions`, `/versions/{v}/yaml`:
  one helper, as today's `_require_contract_read_access`. An unreadable draft
  answers `403` with
  `"This contract is a draft. Only its domain and invited reviewers can read it."`
- `GET /data-contracts/{id}/ports` (usage) keeps the ODPS plan 1 decision: no
  read check, because it lists only product and port names.
- Data product responses keep showing the contract summary of a port (title,
  status, version) as today.

## Layer 2 and 3: Approval and Owner

Transition table (Platform Admin may do every row):

| From | To | Who | Action label |
|---|---|---|---|
| (new) | `draft` | Steward, Owner (members) | New contract: always born `draft` |
| `draft` | `in_review` | Steward (member) | Submit for review |
| `in_review` | `draft` | Steward (member) | Withdraw |
| `in_review` | `draft` | Owner (member) | Request changes |
| `in_review` | `active` | Owner (member) | Approve |
| `active` | `deprecated` | Owner (member) | Deprecate |
| `deprecated` | `active` | Owner (member) | Reactivate |
| `active`, `deprecated` | `retired` | Owner (member) | Retire (terminal, as today) |

Any other pair is refused with `409` and a message naming the allowed actions.

Content edits (`PUT /data-contracts/{id}`):

- Steward (member) and Admin, as today.
- Allowed in `draft`. Refused in `in_review` with `409` ("Withdraw it to edit"):
  the reviewer approves a fixed text.
- `PUT` no longer carries `status`; a request that sends it gets `422`.
  `POST /data-contracts` creates every contract as `draft`. The admin-only GitHub
  sync keeps importing statuses as they are.
- Published contracts (`active`, `deprecated`): see the decision below.

New endpoint: `POST /data-contracts/{id}/status` with `{"status": "<to>"}`.
It runs the transition table, then the same versioning/evolution path as today
(`apply_evolution`), and the same GitHub push.

## Permissions sent to the page

`GET /data-contracts/{id}` gains, for the current user:

```json
"permissions": {
  "edit": true,
  "delete": false,
  "transitions": ["in_review"],
  "manage_stakeholders": true
}
```

`transitions` lists the statuses the user may move this contract to. The page
derives every button from this object. The backend computes it with the same
functions that enforce the rules.

## Stakeholders: reviewers of a draft

A stakeholder is a person invited to read a **draft**, usually the consuming team
that will depend on it (the RBAC spec: "cross-domain visibility and
communication").

API:

- `GET /data-contracts/{id}/stakeholders` (new): readers of the contract may
  call it.
  ```json
  [{ "user_id": "…", "username": "ana", "role": "DATA_CONSUMER",
     "assigned_by_username": "joao", "assigned_at": "…" }]
  ```
  One query (join `iam.users` twice), ordered by `assigned_at`.
- `POST` / `DELETE` exist (Steward member or Admin). They now refuse a published
  contract with `409` ("Published contracts are readable by everyone").
  Re-adding an existing stakeholder is not an error.

## UI

Follows the contract page's existing building blocks: `Panel`, `Avatar`,
`Button` variants, `Modal`, the danger-style Delete button, and the add-member
flow of `pages/Domains/AddMemberModal.tsx` (search + listbox).

**Header actions:** View YAML (everyone), Edit (`permissions.edit`), Delete
(`permissions.delete`).

**Status bar** (replaces today's `ReviewBanner`, same look: rounded, tinted,
icon, text, buttons on the right):

```
draft      ▢ Draft · only Finance and invited reviewers can see it.   [Submit for review]
in_review  ⚠ Awaiting review by the Finance owner.    owner: [Approve] [Request changes]
                                                     steward: [Withdraw]
deprecated ⚠ Deprecated · consumers should move to a newer contract.  owner: [Reactivate] [Retire]
active     (no bar; owner sees "Deprecate" and "Retire" next to Edit)
```

Retire asks for confirmation in a small modal (it is irreversible), like Delete.
Buttons show their loading state while the request runs; errors show in the bar.

**Form:** the status select goes away. A new contract shows the hint "Saved as a
draft. Submit it for review when it is ready."

**Stakeholders panel** (aside, first panel while the contract is `draft` or
`in_review`; hidden once published):

```
┌ 👥 Stakeholders ─────────────── 2 · + Add ┐
│ Can read this draft before it is published. │
│ (A) ana.silva   Consumer · 3 days ago     ✕ │
│ (J) joao.p      Consumer · today          ✕ │
└─────────────────────────────────────────────┘
```

- Empty: "No one invited yet." With manage permission, an "Invite reviewers"
  button instead.
- ✕ removes at once, like domain members. It is reversible by adding again.
- **Add modal:** search by username; members of the contract's domain listed
  first, then everyone else. Users who already read drafts of this contract
  (Platform Admins, Owner/Steward members of the domain) and current
  stakeholders are shown disabled with the reason ("Already reads drafts of
  Finance", "Already invited"). Multiple selection, one "Invite" button.

**Profile page:** the role texts follow the new model (Consumer: "Reads every
published contract; drafts when invited as a stakeholder").

**List page:** consumers see only what they may read, so there are no empty
cards.

## Decision: changes to a published contract

**Decided by the owner:** a Steward edits an `active` or `deprecated` contract
directly, as today. The change is protected by
the existing rules: semver enforcement and the breaking-change checks of the
versioning work (#35), immutable version history, and the consumer's "Switch"
flow on products. Putting every change to a published contract through approval
needs a pending version stored next to the active one, a diff for the reviewer,
and approve/reject of that version. That is a project of its own, and the
README ties it to the tier's evolution policy.

## Testing

- Pure domain module (`backend/domain/contract_access.py`): `can_read` and the
  transition table, table-driven tests over every role × membership × status.
  Mutation-tested like the other domain modules.
- Router tests: list filtering per role, `403` on an unreadable draft for each
  read endpoint, `POST /status` for every allowed and refused pair, `PUT` refusing
  `status` and `in_review` edits, the stakeholder endpoints, and the
  `permissions` object.
- N+1 tests for the list (bulk membership and stakeholder sets) and for the
  stakeholder list query.
- Frontend: the status bar for each status × permission set, the header actions,
  the panel (empty, list, remove, hidden when published), the add modal
  (ordering, disabled reasons, multi-select), the form without status, the
  `403` draft message.
- End to end on an isolated stack: consumer, steward, owner and admin walk a
  contract from draft to retired, and a consumer is invited to a draft.

## Deployment

No migration: statuses and the stakeholders table stay as they are. During the
deploy window the old frontend still sends `status` in `PUT` and gets `422`
until reloaded.
