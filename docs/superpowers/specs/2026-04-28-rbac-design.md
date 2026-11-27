# RBAC Design — Role-Based Access Control

**Date:** 2026-04-28\
**Branch:** feature/roles\
**Status:** Approved

> Contract access (who reads, who moves a contract's status, what a stakeholder
> is) is implemented as described in
> [2026-11-26-contract-access-layers-design.md](2026-11-26-contract-access-layers-design.md),
> which follows this matrix for contracts and adds the approval transitions.

---

## Overview

Every user who registers on the platform currently has unrestricted access to all operations. This spec defines a role-based access control (RBAC) system that scopes what each user can do based on their platform role and their membership in one or more domains.

---

## Approach: Role Column + Domain Principal Membership

Each user has a single platform-level role stored as an enum column on `iam.users`. Domain membership is tracked separately via the existing `iam.principals` (GROUP type) and `iam.principal_memberships` tables. Permissions are enforced at the FastAPI layer via a dependency that checks role + domain context on each request.

---

## Roles

| Role | Description |
|---|---|
| `PLATFORM_ADMIN` | Full access to all resources and operations across the entire platform |
| `DATA_OWNER` | Full control within their own domain: manage members, approve/reject contracts, delete contracts |
| `DATA_STEWARD` | Creates and edits data contracts within their domain; assigns stakeholders to contracts |
| `DATA_CONSUMER` | Read-only access to published resources — **default role for all new users** |

---

## Domain Membership

A domain is a namespace (a GROUP-type principal in `iam.principals`). Users belong to a domain via `iam.principal_memberships`. A user can belong to multiple domains. Their platform role applies within each domain they are a member of.

---

## Permission Matrix

### User Management

| Action | Platform Admin | Data Owner | Data Steward | Data Consumer |
|---|---|---|---|---|
| Delete user from platform | ✅ | ❌ | ❌ | ❌ |
| Assign platform role to any user | ✅ | ❌ | ❌ | ❌ |
| Assign first Data Owner to a domain | ✅ | ❌ | ❌ | ❌ |
| Add/remove members from own domain | ✅ | ✅ own domain | ❌ | ❌ |
| View own profile | ✅ | ✅ | ✅ | ✅ |

### Data Contracts

| Action | Platform Admin | Data Owner | Data Steward | Data Consumer |
|---|---|---|---|---|
| Create contract | ✅ | ❌ | ✅ own domain | ❌ |
| Edit contract | ✅ | ❌ | ✅ own domain | ❌ |
| Approve / reject contract | ✅ | ✅ own domain | ❌ | ❌ |
| Delete contract | ✅ | ✅ own domain | ❌ | ❌ |
| Read published contracts | ✅ | ✅ | ✅ | ✅ |
| Read draft contracts | ✅ | ✅ own domain | ✅ own domain | ❌ |
| Read draft contracts (as Stakeholder) | — | — | — | ✅ on assigned contracts |
| Assign stakeholders to a contract | ✅ | ❌ | ✅ own domain | ❌ |

---

## Stakeholder (per-contract relationship)

A Stakeholder is not a platform role. Any user of any role can be assigned as a Stakeholder on a specific data contract by a Data Steward. Stakeholders gain read access to that contract's drafts, enabling cross-domain visibility and communication. Stored in a dedicated `governance.contract_stakeholders` join table.

---

## Data Model Changes

### 1. Add `role` column to `iam.users`

```sql
ALTER TABLE iam.users
ADD COLUMN role TEXT NOT NULL DEFAULT 'DATA_CONSUMER'
CHECK (role IN ('PLATFORM_ADMIN', 'DATA_OWNER', 'DATA_STEWARD', 'DATA_CONSUMER'));
```

### 2. Domain membership (reuse existing tables)

```
iam.principals          { id, name, type='GROUP' }   -- one row per domain
iam.principal_memberships { user_id, principal_id }  -- user ↔ domain link
```

### 3. New table: `governance.contract_stakeholders`

```sql
CREATE TABLE governance.contract_stakeholders (
  contract_id UUID REFERENCES governance.data_contract(id) ON DELETE CASCADE,
  user_id     UUID REFERENCES iam.users(id) ON DELETE CASCADE,
  assigned_by UUID REFERENCES iam.users(id),
  assigned_at TIMESTAMPTZ DEFAULT now(),
  PRIMARY KEY (contract_id, user_id)
);
```

---

## Architecture Changes (FastAPI / Clean Architecture)

### Interface layer — new permission dependency

`backend/interface/dependencies/permissions.py`

- `require_roles(*roles)` — validates the current user has one of the given platform roles
- `require_domain_role(domain_id, *roles)` — validates role + domain membership
- Applied via FastAPI `Depends()` on each router

### Domain layer

- `User` entity gains `role: UserRole` field
- New `Domain` entity
- New `ContractStakeholder` entity

### Use Cases (new)

- `AssignRoleUseCase` — Admin only; sets a user's platform role
- `AssignDomainMemberUseCase` — Admin or Data Owner (own domain); adds/removes users from a domain
- `AssignStakeholderUseCase` — Admin or Steward (own domain); assigns a user as stakeholder on a contract

### Use Cases (updated)

Existing contract use cases gain permission checks via the permission dependency before executing.

### Infrastructure

- One Atlas migration adding `role` column + `contract_stakeholders` table
- Updated `UserRepository` to read/write the `role` field
- New `DomainRepository`
- New `StakeholderRepository`

---

## New API Endpoints

| Method | Path | Allowed roles |
|---|---|---|
| `PATCH` | `/users/{id}/role` | Platform Admin |
| `POST` | `/domains` | Platform Admin |
| `POST` | `/domains/{id}/members` | Platform Admin, Data Owner (own domain) |
| `DELETE` | `/domains/{id}/members/{user_id}` | Platform Admin, Data Owner (own domain) |
| `POST` | `/contracts/{id}/stakeholders` | Platform Admin, Data Steward (own domain) |
| `DELETE` | `/contracts/{id}/stakeholders/{user_id}` | Platform Admin, Data Steward (own domain) |

### Existing endpoints that gain guards

| Endpoint | Change |
|---|---|
| `DELETE /users/{id}` | Platform Admin only |
| `POST /contracts` | Platform Admin or Data Steward (own domain) |
| `PATCH /contracts/{id}` | Platform Admin or Data Steward (own domain) |
| `POST /contracts/{id}/approve` | Platform Admin or Data Owner (own domain) |
| `DELETE /contracts/{id}` | Platform Admin or Data Owner (own domain) |
| `GET /contracts/{id}` (draft) | Admin, Owner/Steward in domain, or Stakeholder |

---

## Role Assignment Rules

1. **New users** receive `DATA_CONSUMER` automatically on registration.
2. **Platform Admins** can assign any role to any user at any time.
3. **The first Data Owner** for a domain must be assigned by a Platform Admin.
4. **Data Owners** can add or remove members from their own domain after that.
5. **Data Owners** cannot change another user's platform role — only Admins can.
