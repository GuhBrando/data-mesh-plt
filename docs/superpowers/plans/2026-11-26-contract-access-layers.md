# Contract Access Layers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Everyone reads published contracts; drafts are read by the domain and invited stakeholders; stewards propose, the domain's owner approves, and the contract page shows each user only the actions they may take.

**Architecture:** One pure domain module (`backend/domain/contract_access.py`) owns every rule (read, edit, delete, transitions, stakeholders). The router gathers the facts (role, domain membership, stakeholder) and asks it; the detail response carries the result as `permissions`, which the page renders. Status changes move to `POST /data-contracts/{id}/status`, through the existing update use case.

**Tech Stack:** FastAPI + Pydantic v2, asyncpg, pytest; React 18 + TypeScript, TanStack Query, Vitest + Testing Library, Tailwind tokens of the existing UI.

**Spec:** `docs/superpowers/specs/2026-11-26-contract-access-layers-design.md`

## Global Constraints

- Published statuses: `active`, `deprecated`, `retired`. Unpublished: `draft`, `in_review`.
- "Member" means a row in `catalog.domain_members` for the contract's `domain_id` (`is_domain_member`).
- A Platform Admin may do every allowed transition and every action; it never bypasses the transition table.
- No transition from a published status to `draft` or `in_review`, for anyone.
- Unreadable draft detail, verbatim: `This contract is a draft. Only its domain and invited reviewers can read it.`
- `PUT` with `status`, verbatim 422 message: `Change the status with POST /data-contracts/{id}/status`
- Edit while `in_review`, verbatim 409: `This contract is in review. Withdraw it to edit.`
- Stakeholder change on a published contract, verbatim 409: `Published contracts are readable by everyone.`
- `GET /data-contracts/{id}/ports` keeps no read check (ODPS plan 1 decision).
- UI copy is English, as the rest of the frontend. Reuse `Panel`, `Avatar`, `Button`, `Modal`, `relativeTime`, and the look of `ReviewBanner` and `pages/Domains/AddMemberModal.tsx`.
- Commits: conventional messages, no co-author or generated-by lines. On this machine run `git commit` with `PATH="$PWD/.venv/Scripts:$PATH"` so the pre-commit hooks find their tools.

## Review Focus

1. A Data Consumer who is a **member** of the domain still cannot read its drafts (membership counts only for Owner and Steward). Pinned in Task 1 and Task 2.
2. Two people act on the same `in_review` contract at once (Approve and Withdraw): the second request gets `409`, not a silent overwrite. Pinned in Task 3 (`expected_status`).
3. The old frontend, still open after the deploy, sends `status` in `PUT`: it gets the 422 message above, and nothing is saved. Pinned in Task 3.
4. A Steward of **another** domain opens a draft they were invited to: they read it, see no Edit, no status buttons, no Add in the panel. Pinned in Task 4 (permissions) and Task 7.
5. Inviting someone who already reads drafts (Admin, Owner/Steward member) or who is already invited: shown disabled with the reason, never sent. Pinned in Task 7.

---

### Task 1: Access rules module

**Files:**
- Create: `backend/domain/contract_access.py`
- Test: `tests/unit/test_contract_access.py`

**Interfaces:**
- Produces:
  - `PUBLISHED_STATUSES: frozenset[str]`
  - `@dataclass(frozen=True) class ContractActor: role: UserRole; is_member: bool; is_stakeholder: bool = False`
  - `can_read(status: str, actor: ContractActor) -> bool`
  - `can_edit(status: str, actor: ContractActor) -> bool`
  - `can_delete(actor: ContractActor) -> bool`
  - `can_manage_stakeholders(status: str, actor: ContractActor) -> bool`
  - `allowed_transitions(status: str, actor: ContractActor) -> list[str]` (in the order of the spec's table)
  - `class TransitionRefused(Exception)` with attribute `forbidden: bool` (True: the pair exists but this actor may not use it → 403; False: no such pair → 409)
  - `check_transition(current: str, target: str, actor: ContractActor) -> None`

Rules (from the spec): read = published, or Admin, or Owner/Steward member, or stakeholder. Edit = (Admin or Steward member) and status in `draft`, `active`, `deprecated`. Delete = Admin or Owner member. Manage stakeholders = status unpublished and (Admin or Steward member). Transitions as a table `{(from, to): frozenset of "steward"/"owner"}`:
`(draft,in_review)`: steward · `(in_review,draft)`: steward, owner · `(in_review,active)`: owner · `(active,deprecated)`: owner · `(deprecated,active)`: owner · `(active,retired)`: owner · `(deprecated,retired)`: owner. "steward" = Steward member, "owner" = Owner member; Admin passes every pair in the table.

Messages: no pair → `A {current} contract cannot move to {target}.`; forbidden → `You cannot move this contract from {current} to {target}.`

- [ ] **Step 1: Write the failing tests** (table-driven)

```python
ADMIN = ContractActor(UserRole.PLATFORM_ADMIN, is_member=False)
OWNER = ContractActor(UserRole.DATA_OWNER, is_member=True)
STEWARD = ContractActor(UserRole.DATA_STEWARD, is_member=True)
OUTSIDE_STEWARD = ContractActor(UserRole.DATA_STEWARD, is_member=False)
MEMBER_CONSUMER = ContractActor(UserRole.DATA_CONSUMER, is_member=True)
INVITED = ContractActor(UserRole.DATA_CONSUMER, is_member=False, is_stakeholder=True)

@pytest.mark.parametrize("status", ["active", "deprecated", "retired"])
def test_everyone_reads_published(status):
    assert can_read(status, ContractActor(UserRole.DATA_CONSUMER, is_member=False))

@pytest.mark.parametrize("actor, expected", [
    (ADMIN, True), (OWNER, True), (STEWARD, True), (INVITED, True),
    (OUTSIDE_STEWARD, False), (MEMBER_CONSUMER, False),
])
@pytest.mark.parametrize("status", ["draft", "in_review"])
def test_drafts_are_read_by_the_domain_and_invited(status, actor, expected):
    assert can_read(status, actor) is expected

def test_published_never_goes_back_to_unpublished():
    for status in PUBLISHED_STATUSES:
        for actor in (ADMIN, OWNER, STEWARD):
            assert not set(allowed_transitions(status, actor)) & {"draft", "in_review"}

@pytest.mark.parametrize("status, actor, expected", [
    ("draft", STEWARD, ["in_review"]), ("draft", OWNER, []),
    ("in_review", STEWARD, ["draft"]), ("in_review", OWNER, ["draft", "active"]),
    ("in_review", ADMIN, ["draft", "active"]),
    ("active", OWNER, ["deprecated", "retired"]), ("active", STEWARD, []),
    ("deprecated", OWNER, ["active", "retired"]), ("retired", ADMIN, []),
    ("in_review", OUTSIDE_STEWARD, []),
])
def test_allowed_transitions(status, actor, expected):
    assert allowed_transitions(status, actor) == expected

def test_check_transition_forbidden_vs_unknown():
    with pytest.raises(TransitionRefused) as forbidden:
        check_transition("in_review", "active", STEWARD)
    assert forbidden.value.forbidden is True
    with pytest.raises(TransitionRefused) as unknown:
        check_transition("active", "draft", ADMIN)
    assert unknown.value.forbidden is False
    assert str(unknown.value) == "A active contract cannot move to draft."
```

Plus parametrized tests for `can_edit` (Steward member: draft/active/deprecated True, in_review/retired False; Owner False; Admin same statuses as Steward), `can_delete` (Admin, Owner member True; Owner non-member, Steward False) and `can_manage_stakeholders` (Steward member and Admin on draft/in_review True, on active False; Owner False).

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/unit/test_contract_access.py -q`
Expected: FAIL, `ModuleNotFoundError: backend.domain.contract_access`

- [ ] **Step 3: Implement the module** with the signatures and table above. No I/O.

- [ ] **Step 4: Run them to see them pass**

Run: `uv run pytest tests/unit/test_contract_access.py -q` → all pass.

- [ ] **Step 5: Commit**

```bash
git add backend/domain/contract_access.py tests/unit/test_contract_access.py
git commit -m "feat(domain): contract access rules for readers, approvers and owners"
```

---

### Task 2: Read access on the contract API

**Files:**
- Modify: `backend/interface/permissions.py` (add `member_domain_ids`)
- Modify: `backend/interface/routers/data_contract.py` (`_require_contract_read_access`, `_readable_ids`, `_RESTRICTED_SECTIONS`, list, detail, yaml, versions, version yaml)
- Test: `tests/unit/interface/test_routers.py`, `tests/unit/test_n1_detection.py`

**Interfaces:**
- Consumes: Task 1 `ContractActor`, `can_read`, `PUBLISHED_STATUSES`.
- Produces:
  - `member_domain_ids(user_id: uuid.UUID, db) -> set[uuid.UUID]` (one query on `catalog.domain_members`)
  - router helper `_actor(contract: DataContract, user: User, db, stakeholder_repo) -> ContractActor`: queries membership only for Owner/Steward; queries `is_stakeholder` only when the contract is unpublished and the actor cannot already read it.
  - router helper `_readable_contract(contract_id, user, get_use_case, stakeholder_repo, db) -> DataContract`: 404 when missing, 403 with the verbatim draft message when `can_read` is False.

Remove `_RESTRICTED_SECTIONS` and the section stripping. The list keeps published contracts and keeps an unpublished one only when the user may read it: Admin → all; otherwise one `member_domain_ids` call (Owner/Steward only) and one `contract_ids_of` call, made only when the list holds an unpublished contract. The version endpoints now load the contract (add `GetDataContractUseCase` to their dependencies) before deciding.

- [ ] **Step 1: Write the failing tests** (replace the stakeholder-only tests at `test_routers.py:474-531` and `:760-772`)

```python
@pytest.mark.parametrize("path", ["", "/yaml", "/versions"])
def test_consumer_reads_a_published_contract(consumer_client, path):
    _reads(contract=_contract(status="active"))
    assert consumer_client.get(f"/api/v1/data-contracts/{CONTRACT_ID}{path}").status_code == 200

@pytest.mark.parametrize("path", ["", "/yaml", "/versions", "/versions/1.0.0/yaml"])
def test_consumer_outside_a_draft_gets_the_draft_message(consumer_client, path):
    _reads(contract=_contract(status="draft"), stakeholder=False)
    resp = consumer_client.get(f"/api/v1/data-contracts/{CONTRACT_ID}{path}")
    assert resp.status_code == 403
    assert resp.json()["detail"] == (
        "This contract is a draft. Only its domain and invited reviewers can read it.")

def test_invited_consumer_reads_the_draft(consumer_client):
    _reads(contract=_contract(status="in_review"), stakeholder=True)
    assert consumer_client.get(f"/api/v1/data-contracts/{CONTRACT_ID}").status_code == 200

def test_list_shows_published_in_full_and_hides_unreadable_drafts(consumer_client):
    published = _contract(id=uuid.uuid4(), status="active", **STORED)
    draft = _contract(id=uuid.uuid4(), status="draft")
    invited = _contract(id=uuid.uuid4(), status="in_review")
    _list(contracts=[published, draft, invited], stakeholder_of={invited.id})
    listed = consumer_client.get("/api/v1/data-contracts").json()
    assert [c["id"] for c in listed] == [str(published.id), str(invited.id)]
    assert listed[0]["servers"] == STORED["servers"]
```

`_contract` gains a `status` keyword (default `"draft"`). `_reads` and `_list` are small helpers in the test module that override `get_get_data_contract_use_case`, the version use cases, `get_stakeholder_repository` (`is_stakeholder`, `contract_ids_of`) and `get_db_connection` (`fetchrow`/`fetch` for membership). Add a member-steward case (`db.fetch` returns the domain id) that lists a draft of their domain, and a member **consumer** case that does not (Review Focus 1).

In `test_n1_detection.py`: `member_domain_ids` makes exactly one call, following `test_contracts_by_ids_is_one_query`.

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/unit/interface/test_routers.py tests/unit/test_n1_detection.py -q`
Expected: the new tests FAIL (published contract → 403 for a consumer today; list strips sections).

- [ ] **Step 3: Implement** `member_domain_ids`, `_actor`, `_readable_contract`, the list filter; delete `_readable_ids` and `_RESTRICTED_SECTIONS`.

- [ ] **Step 4: Run the whole backend unit suite**

Run: `uv run pytest tests/unit -q` → all pass.

- [ ] **Step 5: Commit**

```bash
git add backend/interface tests/unit
git commit -m "feat(api): everyone reads published contracts; drafts stay with their domain and stakeholders"
```

---

### Task 3: Status changes go through the transition table

**Files:**
- Modify: `backend/domain/contract_evolution.py` (two errors)
- Modify: `backend/use_cases/data_contract/update.py`
- Modify: `backend/interface/schemas/data_contract.py` (create/update status, new `ContractStatusChangeModel`)
- Modify: `backend/interface/routers/data_contract.py` (new endpoint; PUT uses `can_edit`)
- Test: `tests/unit/use_cases/data_contract/test_versioning.py` (where the update use case is tested under its lock), `tests/unit/interface/test_routers.py`

**Interfaces:**
- Consumes: Task 1 `can_edit`, `check_transition`, `TransitionRefused`; Task 2 `_actor`.
- Produces:
  - `class ContractInReviewError(ContractEvolutionError)`, message `This contract is in review. Withdraw it to edit.`
  - `class ContractStatusConflictError(ContractEvolutionError)`, message `The contract is now {status}. Reload and try again.`
  - `UpdateDataContractUseCase.execute(contract_id, changes, created_by=None, expected_status: str | None = None) -> UpdatedContract | None`: under the row lock, raises `ContractStatusConflictError` when `expected_status` is set and differs from the locked status; raises `ContractInReviewError` when the locked status is `in_review` and `changes` holds any key other than `status`.
  - `ContractStatusChangeModel(BaseModel)`: `status: Literal["draft", "in_review", "active", "deprecated", "retired"]`
  - `POST /data-contracts/{contract_id}/status` → `DataContractResponseModel` (with `permissions`, Task 4). Order: load (404) → `_actor` → `check_transition` (403 when `forbidden`, else 409, message from the exception) → `execute(..., changes={"status": target}, expected_status=current)` → GitHub push `"Update contract"` → response.
  - `DataContractCreateModel.status: Literal["draft"] = "draft"`.
  - `DataContractUpdateModel.status` stays declared; a `field_validator` rejects any non-None value with the verbatim 422 message.
  - `PUT` keeps its guard (Steward member or Admin). The use case refuses `in_review` edits (`ContractInReviewError` → 409) and retired ones (today's `RetiredContractError`).

- [ ] **Step 1: Write the failing tests**

```python
async def test_status_moves_only_from_the_expected_status(repo):
    repo.locked = _contract(status="draft")  # someone withdrew it meanwhile
    with pytest.raises(ContractStatusConflictError, match="The contract is now draft"):
        await UpdateDataContractUseCase(repo).execute(
            CONTRACT_ID, {"status": "active"}, expected_status="in_review")

async def test_no_edit_while_in_review_but_status_moves(repo):
    repo.locked = _contract(status="in_review")
    with pytest.raises(ContractInReviewError):
        await UpdateDataContractUseCase(repo).execute(CONTRACT_ID, {"title": "New"})
    assert await UpdateDataContractUseCase(repo).execute(
        CONTRACT_ID, {"status": "draft"}, expected_status="in_review")
```

Router tests:

```python
@pytest.mark.parametrize("role, member, current, target, code", [
    (UserRole.DATA_STEWARD, True, "draft", "in_review", 200),
    (UserRole.DATA_STEWARD, True, "in_review", "active", 403),
    (UserRole.DATA_OWNER, True, "in_review", "active", 200),
    (UserRole.DATA_OWNER, False, "in_review", "active", 403),
    (UserRole.PLATFORM_ADMIN, False, "active", "draft", 409),
    (UserRole.DATA_CONSUMER, True, "draft", "in_review", 403),
])
def test_status_change(role, member, current, target, code): ...
    # asserts status code; on 200, the use case got changes={"status": target},
    # expected_status=current, and GitHub push was called once

def test_put_with_status_is_refused(admin_client):
    resp = admin_client.put(f"/api/v1/data-contracts/{CONTRACT_ID}", json={"status": "active"})
    assert resp.status_code == 422
    assert "Change the status with POST /data-contracts/{id}/status" in resp.text

def test_create_is_always_a_draft(admin_client):
    # POST with status "active" → 422; without status → use case gets status "draft"
```

Delete `test_status_only_put_sends_only_the_status` and `test_update_accepts_retired_status`; the endpoint test covers both moves.

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/unit -q -k "status or in_review or create_is_always"` → the new tests FAIL.

- [ ] **Step 3: Implement** the errors, `expected_status`, the in-review guard, the schema changes, the endpoint and the PUT guard.

- [ ] **Step 4: Run the whole backend unit suite** → `uv run pytest tests/unit -q` passes.

- [ ] **Step 5: Commit**

```bash
git add backend tests/unit
git commit -m "feat(api): contract status moves through the approval table; the owner approves"
```

---

### Task 4: Permissions on the contract detail

**Files:**
- Modify: `backend/interface/schemas/data_contract.py` (`ContractPermissionsModel`, optional field on the response)
- Modify: `backend/interface/routers/data_contract.py` (detail and `POST .../status` fill it)
- Test: `tests/unit/interface/test_routers.py`

**Interfaces:**
- Consumes: Task 1 `can_edit`, `can_delete`, `allowed_transitions`, `can_manage_stakeholders`; Task 2 `_actor`.
- Produces: `ContractPermissionsModel`: `edit: bool`, `delete: bool`, `transitions: list[str]`, `manage_stakeholders: bool`; `DataContractResponseModel.permissions: ContractPermissionsModel | None = None` (only detail and status responses fill it; the list leaves it `None`).

- [ ] **Step 1: Write the failing tests**

```python
@pytest.mark.parametrize("role, member, status, expected", [
    (UserRole.DATA_STEWARD, True, "draft",
     {"edit": True, "delete": False, "transitions": ["in_review"], "manage_stakeholders": True}),
    (UserRole.DATA_OWNER, True, "in_review",
     {"edit": False, "delete": True, "transitions": ["draft", "active"], "manage_stakeholders": False}),
    (UserRole.DATA_STEWARD, False, "in_review",  # invited steward of another domain
     {"edit": False, "delete": False, "transitions": [], "manage_stakeholders": False}),
    (UserRole.DATA_CONSUMER, False, "active",
     {"edit": False, "delete": False, "transitions": [], "manage_stakeholders": False}),
])
def test_detail_carries_the_callers_permissions(role, member, status, expected): ...
```

- [ ] **Step 2: Run it to see it fail** → `uv run pytest tests/unit/interface/test_routers.py -q -k permissions`
- [ ] **Step 3: Implement** the model and fill it in both responses.
- [ ] **Step 4: Run the backend unit suite** → passes.
- [ ] **Step 5: Commit**

```bash
git add backend tests/unit
git commit -m "feat(api): the contract detail says what the caller may do"
```

---

### Task 5: Stakeholder list and guards

**Files:**
- Create: `backend/domain/entities/stakeholder_view.py`
- Modify: `backend/domain/interfaces/stakeholder_repository.py`, `backend/infra/repositories/stakeholder_repository.py`
- Modify: `backend/interface/schemas/stakeholder.py`, `backend/interface/routers/data_contract.py`
- Test: `tests/unit/interface/test_routers.py`, `tests/unit/test_n1_detection.py`, new `tests/integration/test_stakeholder_repository.py` (runs with `TEST_DATABASE_URL`, like `test_data_product_repository.py`)

**Interfaces:**
- Consumes: Task 1 `can_manage_stakeholders`; Task 2 `_readable_contract`, `_actor`.
- Produces:
  - `@dataclass(frozen=True) class StakeholderView: user_id: uuid.UUID; username: str; role: str; assigned_by_username: str; assigned_at: datetime`
  - `IStakeholderRepository.list_for_contract(contract_id: uuid.UUID) -> list[StakeholderView]`: one query, `iam.users` joined for the stakeholder (`name` as username, `role`) and left-joined for `assigned_by` (`''` when null), ordered by `assigned_at`.
  - `StakeholderViewModel` (same fields) and `GET /data-contracts/{contract_id}/stakeholders -> list[StakeholderViewModel]`, guarded by `_readable_contract`.
  - `POST` and `DELETE` stakeholders: any signed-in user reaches the handler; it loads the contract, answers 409 with the verbatim published message when the status is published, then 403 unless `can_manage_stakeholders`.

- [ ] **Step 1: Write the failing tests**

```python
def test_list_stakeholders(admin_client):
    # repo.list_for_contract returns one StakeholderView → JSON has username, role,
    # assigned_by_username, assigned_at

@pytest.mark.parametrize("method", ["post", "delete"])
def test_stakeholders_frozen_once_published(admin_client, method):
    # contract status "active" → 409, detail "Published contracts are readable by everyone."

@pytest.mark.parametrize("role, member, code", [
    (UserRole.DATA_STEWARD, True, 201), (UserRole.DATA_STEWARD, False, 403),
    (UserRole.DATA_OWNER, True, 403), (UserRole.PLATFORM_ADMIN, False, 201),
])
def test_who_invites(role, member, code): ...
```

N+1: `list_for_contract` is a single `fetch`.

- [ ] **Step 2: Run them to see them fail** → `uv run pytest tests/unit -q -k stakeholder`
- [ ] **Step 3: Implement** the view, the repository method, the endpoint and the guards.
- [ ] **Step 4: Run the backend unit suite** → passes. With `TEST_DATABASE_URL` set (Docker Postgres recipe), run the integration test for `list_for_contract` → passes.
- [ ] **Step 5: Commit**

```bash
git add backend tests
git commit -m "feat(api): list a draft's stakeholders; only the domain's steward invites them"
```

---

### Task 6: Contract page actions and status bar

**Files:**
- Modify: `frontend/src/types/index.ts` (`ContractPermissions`, `DataContract.permissions?`, `DataContractInput` without `status`)
- Modify: `frontend/src/hooks/useDataContracts.ts` (`useChangeContractStatus`)
- Create: `frontend/src/pages/DataContracts/StatusBar.tsx`
- Modify: `frontend/src/pages/DataContracts/DataContractDetail.tsx` (header actions, StatusBar, retire confirm, draft 403 message; remove `ReviewBanner`)
- Modify: `frontend/src/pages/DataContracts/DataContractForm.tsx` (remove `StatusSelect` and `status` from schema and payload; hint on create)
- Test: `frontend/src/pages/DataContracts/StatusBar.test.tsx`, `DataContractDetail.test.tsx`, `DataContractForm.test.tsx`

**Interfaces:**
- Consumes: Task 4 `permissions`; Task 3 `POST /data-contracts/{id}/status`.
- Produces:
  - `interface ContractPermissions { edit: boolean; delete: boolean; transitions: DataContract['status'][]; manage_stakeholders: boolean }`
  - `useChangeContractStatus(): UseMutationResult<DataContract, Error, { id: string; status: DataContract['status'] }>`; on success invalidates `KEYS.all`, `KEYS.one(id)`, `KEYS.yaml(id)`, `KEYS.versions(id)`.
  - `StatusBar({ contract, pending, error, onMove }: { contract: DataContract; pending: boolean; error: string | null; onMove: (to: DataContract['status']) => void })`

Copy (verbatim): draft `Draft · only {domain} and invited reviewers can see it.` + `Submit for review`; in_review `Awaiting review by the {domain} owner.` + `Approve`, `Request changes` (when `active` in transitions) or `Withdraw` (steward: `draft` in transitions without `active`); deprecated `Deprecated · consumers should move to a newer contract.` + `Reactivate`, `Retire`; active → no bar, header gets `Deprecate` and `Retire` when allowed. A button appears only when its target is in `permissions.transitions`; a bar with no buttons still shows its text (draft/in_review/deprecated). Retire opens a `Modal` titled `Retire contract` with `Retiring is permanent: the contract can no longer be edited or reactivated.` and `Cancel` / `Retire` (danger style of Delete). Header: `View YAML` always; `Edit` only with `permissions.edit`; `Delete` only with `permissions.delete`. Create form hint: `Saved as a draft. Submit it for review when it is ready.` A detail load that fails with the draft 403 shows the API message instead of `Contract not found`.

- [ ] **Step 1: Write the failing tests**

```tsx
it.each([
  ['draft', ['in_review'], 'Draft · only commerce and invited reviewers can see it.', ['Submit for review']],
  ['in_review', ['draft', 'active'], 'Awaiting review by the commerce owner.', ['Approve', 'Request changes']],
  ['in_review', ['draft'], 'Awaiting review by the commerce owner.', ['Withdraw']],
  ['in_review', [], 'Awaiting review by the commerce owner.', []],
  ['deprecated', ['active', 'retired'], 'Deprecated · consumers should move to a newer contract.', ['Reactivate', 'Retire']],
])('status bar for %s with %j', (status, transitions, text, buttons) => { /* render StatusBar, assert text and exact button names */ })

it('approving sends the target status', async () => { /* click Approve → onMove('active') */ })
it('retire asks for confirmation before moving', async () => { /* Retire → dialog "Retire contract" → Retire → mutate({ id, status: 'retired' }) */ })
it('hides Edit and Delete without permission', () => { /* permissions all false → only "View YAML" */ })
it('shows the draft message when the API refuses', () => { /* useDataContract error.message = draft detail → text shown */ })
// DataContractForm: no "Status" field; create submit payload has no "status"; hint text present on create only
```

- [ ] **Step 2: Run them to see them fail**

Run (in `frontend/`): `npx vitest run src/pages/DataContracts` → new tests FAIL.

- [ ] **Step 3: Implement** types, hook, `StatusBar`, page and form changes. Remove `ReviewBanner` and its tests.

- [ ] **Step 4: Run frontend checks**

Run: `npx vitest run && npm run lint && npm run build` → all pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src
git commit -m "feat(frontend): contract status bar and actions follow the caller's permissions"
```

---

### Task 7: Stakeholders panel and invite modal

**Files:**
- Modify: `frontend/src/types/index.ts` (`Stakeholder`)
- Create: `frontend/src/hooks/useContractStakeholders.ts`
- Create: `frontend/src/pages/DataContracts/StakeholdersPanel.tsx`, `frontend/src/pages/DataContracts/InviteStakeholdersModal.tsx`
- Modify: `frontend/src/pages/DataContracts/DataContractDetail.tsx` (panel first in the aside while unpublished)
- Test: `StakeholdersPanel.test.tsx`, `InviteStakeholdersModal.test.tsx`

**Interfaces:**
- Consumes: Task 5 `GET/POST/DELETE /data-contracts/{id}/stakeholders`; Task 6 `ContractPermissions`; existing `useUsers`, `useDomains`, `Avatar`, `relativeTime`, `Modal`, `Input`, `Button`.
- Produces:
  - `interface Stakeholder { user_id: string; username: string; role: string; assigned_by_username: string; assigned_at: string }`
  - `useContractStakeholders(id: string, enabled: boolean)`, `useInviteStakeholders(id)` (mutation taking `string[]`, one POST per id, invalidates the list), `useRemoveStakeholder(id)` (mutation taking a user id).
  - `StakeholdersPanel({ contract }: { contract: DataContract })` renders nothing when the status is published.
  - `InviteStakeholdersModal({ contract, stakeholders, open, onClose })`.

Copy (verbatim): title `Stakeholders`, helper `Can read this draft before it is published.`, empty `No one invited yet.`, header action `Add` (with manage permission), empty-state button `Invite reviewers` (with manage permission), row `{username}` + `{Admin|Owner|Steward|Consumer} · {relativeTime(assigned_at)}`, remove button aria-label `Remove {username}`. Modal title `Invite reviewers`, search label `Search users`, placeholder `Type a username…`, groups `Members of {domain}` then `Everyone else`, disabled reasons `Already reads drafts of {domain}` (Platform Admins; Owner/Steward members of the domain) and `Already invited`, multi-select, submit `Invite` disabled until one is selected, errors shown like `AddMemberModal`.

- [ ] **Step 1: Write the failing tests**

```tsx
it('lists stakeholders with role and time', () => { /* "ana" and "Consumer · …" */ })
it('is hidden once the contract is published', () => { /* status active → no "Stakeholders" heading */ })
it('offers Add and remove only with manage permission', () => { /* manage_stakeholders false → no "Add", no "Remove ana" */ })
it('removes at once', async () => { /* click "Remove ana" → remove.mutate('u-ana') */ })
it('orders domain members first and disables who already has access', () => {
  /* users: admin (PLATFORM_ADMIN), sam (DATA_STEWARD, member), ana (DATA_CONSUMER, member, already invited),
     bob (DATA_CONSUMER, member), zoe (DATA_CONSUMER, not member)
     → under "Members of commerce": sam disabled "Already reads drafts of commerce",
       ana disabled "Already invited", bob enabled; under "Everyone else": admin disabled, zoe enabled */
})
it('invites every selected user', async () => { /* select bob and zoe → Invite → mutate(['u-bob','u-zoe']) → closes */ })
```

- [ ] **Step 2: Run them to see them fail** → `npx vitest run src/pages/DataContracts` → FAIL.
- [ ] **Step 3: Implement** hooks, panel, modal; mount the panel first in the aside for `draft`/`in_review`.
- [ ] **Step 4: Run frontend checks** → `npx vitest run && npm run lint && npm run build` pass.
- [ ] **Step 5: Commit**

```bash
git add frontend/src
git commit -m "feat(frontend): stakeholders panel invites reviewers to a draft"
```

---

### Task 8: Role texts, docs and end-to-end check

**Files:**
- Modify: `frontend/src/pages/Profile.tsx` (role descriptions)
- Modify: `docs/superpowers/specs/2026-04-28-rbac-design.md` (one line pointing to the new spec)
- Add: this plan and the spec (already in the branch)

Profile copy (verbatim):
- Data Owner permissions: `Add and remove members within your domain`, `Approve, deprecate, retire and delete contracts in your domain`, `View published contracts and your domain's drafts`.
- Data Steward permissions: `Create and edit data contracts within your domain`, `Submit drafts for review and invite reviewers`, `View published contracts and your domain's drafts`.
- Data Consumer description: `Reads every published contract; drafts when invited as a stakeholder.`; permissions: `View every published data contract`, `View drafts you are invited to review`, `View your own profile and domain memberships`.

- [ ] **Step 1: Add `frontend/src/pages/Profile.test.tsx`** asserting the Data Consumer description and one new permission line per role; run → FAIL; change `Profile.tsx`; run → PASS.
- [ ] **Step 2: Full suites**

Run: `uv run pytest tests -q --cov=backend --cov-fail-under=80` (with `TEST_DATABASE_URL`), `uv run ruff check backend`, `uv run ruff format --check backend tests`; in `frontend/`: `npx vitest run --coverage && npm run lint && npm run build`. Expected: all pass, coverage gates met.

- [ ] **Step 3: End to end on an isolated stack** (fresh-volume compose recipe, own network)

Create admin, owner (member), steward (member), consumer (member) and an outside consumer. Check: steward creates → draft; outside consumer does not list it and gets the draft 403; steward invites the outside consumer → they read it; steward submits; steward cannot approve (403); owner approves; outside consumer still reads; consumer member reads; owner deprecates, reactivates, retires; `PUT` with `status` → 422.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/Profile.tsx frontend/src/pages/Profile.test.tsx docs/superpowers
git commit -m "docs: contract access layers spec and plan; role texts follow the new model"
```
