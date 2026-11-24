# ODPS Adoption Design

**Date:** 2026-11-24
**Status:** Draft
**Target standards:** Open Data Product Standard (ODPS) `v1.1.0` (Bitol), with the
Open Data Contract Standard (ODCS) `v3.2.0` the platform already emits
**Baseline:** `develop` at `b54f6d7`, 760 backend tests passing

---

## Overview

A data product today is a name, a description and exactly one data contract
(`catalog.data_products.data_contracts_id`, `NOT NULL`). That cannot describe what
a product really is: it may publish several tables, it reads other products' data,
and some of what it publishes has no contract at all.

ODPS models a product as **input ports** and **output ports**. Each port may
reference an ODCS contract by `contractId` and `version`, and two products are
linked only through a contract: the producer's output port and the consumer's
input port point at the same contract version.

This design makes the platform's data product faithful to ODPS `v1.1.0`, field by
field, while keeping ODCS `v3.2.0` contracts as they are. It is delivered as three
plans. Each leaves the platform working, and each ships the screens that make its
features easy to use day to day.

The owner's intent, in their words: keep it "o mais fidedigno ao ODPS e ao ODCS",
and give the new features "um foco em UI/UX também para facilitar no dia a dia do
usuário da plataforma".

---

## Decisions Made With the Owner (2026-11-23/24)

1. **The contract belongs to the output port, not to the product.** A product that
   publishes two tables has two contracts.
2. **The link between products is the contract.** No field points from one product
   to another. ODPS has none, and ODCS deprecated `dataProduct` in `v3.1.0`.
3. **Rule 1: a product has at least one output port.** ODPS says so in prose ("a data
   product without output is useless"). A routine that only works inside a product is
   part of that product, not a product of its own.
4. **Rule 2: the contract is optional on any output port.** An output without a
   contract (an alert, a write to an external system) is valid but cannot be consumed
   by other products through the platform.
5. **Rule 3: an input port with a `contractId` must point at a contract and version
   that exist on the platform. An input port without one is an external source**
   (a core banking database, a SaaS API, a partner file), recorded by name, linked to
   nothing.
6. **Product status uses the ODPS values:** `proposed`, `draft`, `active`,
   `deprecated`, `retired`.
7. **The whole ODPS product is adopted now (option B)**, in plans, the way ODCS was.
   This includes the fields first proposed for later: `context`, `synonyms`, `sbom`,
   `managementPorts`, `tenant` and variables.
8. **Storage is relational (approach 1)**, like the contract: columns and JSONB on
   the product, one row per port, foreign keys for the contract references.
9. **Every plan carries UI/UX work** aimed at the platform user's daily routine.

## Calls Made by the Designer

The owner accepted these when they were proposed; they are listed so a reviewer can
find them. Calls marked *new* were made while writing this document.

1. `outputPorts[].inputContracts` may only cite contract versions the product itself
   declares as input ports. ODPS is silent.
2. **Rule 4:** an input port cannot be pointed at a contract whose status is
   `retired`; a `deprecated` contract only raises a warning. Status lives on the
   contract, not on the version (`catalog.data_contracts.status`), so the check reads
   the contract's current status when the port is written. A port that already
   points at a contract that is later retired stays, flagged.
3. Existing products migrate to: the domain of their current contract, status
   `active`, and one output port carrying that contract and its current version.
4. *New:* where the ODPS prose and its JSON Schema disagree, the platform follows the
   stricter one. See [Standard Notes](#standard-notes).
5. *New:* a port's version is **pinned**. A new contract version does not move any
   port; the UI offers the move (see Plan 1 screens).
6. *New:* ports are written together with their product (create and full-replace
   update), matched by their key so that a port keeps its `id` across edits.
7. *New:* the product-level `deprecated` flag is derived from status
   (`deprecated` or `retired` → `true`), so the two can never disagree. Ports keep
   their own flag, since ODPS gives ports no status.
8. *New:* the same contract may be the output of two products. It is allowed, and the
   UI warns. An output contract from another domain than the product's is allowed,
   and the UI warns.
9. *New:* **version moves add a port row on both sides.** The producer's "Publish"
   and the consumer's "Switch" each add a row with the new version; the old row stays
   until nothing uses it (no consumer for an output, no `input_contracts` entry for
   an input), then the UI offers to remove it. This is what the ODPS examples show
   (the same input listed at 1.0.0 and 2.0.0) and keeps history true: an output
   version never claims an input version it was not built from. One mechanism serves
   both sides.
10. *New:* **who may pick what.** The rule the product form applies today
    (`selectableContracts` in `frontend/src/lib/domains.ts`: only contracts of domains
    the user belongs to, admins see all) stays for everything the product does on its
    own behalf: the product's domain list and the output contract picker. The input
    picker lists every contract of every domain, because consuming across domains is
    the point. This stays a frontend rule, as today (backend role checks are a
    non-goal).
11. *New:* **Plan 2 ships in a release after one that contains Plan 1 has been
    deployed** to every environment, the same gate the ODCS design set for its
    central-repository conversion. Plan 2's migration drops `data_contracts_id`, which
    only Plan 1's backfill empties; shipped together, the migration would stop before
    the backfill runs and the backend would not start. The migration's guard (stop
    with a clear error while any row has the column set) stays as the safety net.

---

## Goals

- A data product round-trips to an ODPS `v1.1.0` document that validates against
  the official JSON Schema and follows the prose rules adopted here.
- Lineage is queryable: which products produce and consume a contract version, and
  what each product reads and publishes.
- Contract references cannot dangle: the database refuses a port that points at a
  contract version that does not exist, and a contract that a port uses cannot be
  deleted.
- Creating and maintaining a product stays a short, guided flow in the UI, with the
  rules explained in plain language where they bite.

## Non-goals

- Products as YAML in Git (a central products repository, sync, pull requests). The
  platform database stays the source of truth for products; ODPS is an export.
- Importing an ODPS document into the platform (`from_odps`).
- Interpolating ODPS variables. Strings containing `${VAR}` are stored and exported
  verbatim; resolving them is the consuming tool's job.
- Runtime behaviour behind ports: provisioning tables, calling management endpoints,
  running SBOM scans.
- Role checks on the data product routes (any authenticated user may write today,
  as the ODCS design also left out). Ports do not add permissions: declaring that a
  product consumes a contract needs no approval from the producer.
- Updating `database/schema/*.hcl`, which is already out of date with the migrations.
- MCP.

## Anti-goals

- A product form so long that registering a simple product becomes a chore. Advanced
  ODPS sections must stay out of the way until someone needs them.
- Platform-only fields in the exported document. Anything ODPS cannot hold stays out
  of the export, rather than leaking through `customProperties`.

---

## Engineering Principles

The owner asked for clean code, KISS and DDD, no redundancy, few lines of code and
speed. In this codebase that means the following, and every plan is reviewed
against it.

**Domain-driven design**

- `DataProduct` is the **aggregate root**. Its input, output and management ports
  belong to it: they are created, changed and removed only through the product and
  saved with it in one transaction. Nothing else writes the port tables.
- A contract is **another aggregate**, referenced only by `(contract_id, version)`.
  The product never loads or changes a contract.
- **Ubiquitous language:** ODPS names end to end, in entities, API, TypeScript types
  and UI labels: `InputPort`, `OutputPort`, `ManagementPort`, `contract_id`,
  `version`, `input_contracts`. No synonyms ("binding", "link", "dependency") for the
  same thing.
- The layering stays as it is. Entities and domain rules are pure (no I/O, no
  FastAPI, no asyncpg). Domain failures are domain exceptions; routers translate them
  to HTTP.

**KISS and no redundancy**

- **Each rule has exactly one owner**, listed in [Rules](#rules-and-where-they-live):
  - the aggregate for invariants of the product itself, in memory;
  - a declarative database constraint (foreign key, unique, check) for references
    to other aggregates and for structural integrity;
  - the use case only for what needs another aggregate's state (rule 4).
- No rule is written twice in backend code. No triggers. A constraint violation
  becomes a domain error in one place: the repository, through one map from
  constraint name to error.
- **The one deliberate mirror** is the frontend form. Its zod schema repeats only the
  rules a user can break while typing (required fields, rule 1, duplicate port
  names), so the message shows before submit. It never re-derives server state.
- No abstraction with a single user, no option nobody asked for, no new runtime
  dependency.

**Fewer lines**

- **Reuse before writing.** ODPS `team`, `support`, `customProperties` and
  `authoritativeDefinitions` are the ODCS structures. The contract code that handles
  them (key sets and `_filled` in `odcs.py`; `TeamMembers`, `SupportChannels`,
  `EditableRows` in the frontend) is extracted into shared helpers and components and
  used by both, never copied.
- **One mapping drives the export.** A single table from column name to ODPS key
  serializes every JSONB section, instead of one function per section.
- **JSONB unless a rule needs a column.** Only ports and management ports are tables,
  because they carry foreign keys and keys. Every other ODPS section is a JSONB column
  stored as validated.
- **Delete what the change makes dead:** the `data_contracts_id` code paths, the
  single-contract wiring of the product form, the unused `platform` tables.

**Speed**

- A request runs in one transaction with a fixed number of queries, whatever the
  number of ports:
  - ports are written in one batched statement and read with their product in one
    query;
  - the product list and the contract usage endpoint are one query each;
  - rule 4 reads the status of every referenced contract in one query.
- Each new repository method gets an `n1` test, run by the CI's N+1 job.
- Indexes cover the new lookups: ports by `data_product_id`, and ports by
  `(contract_id, version)` for usage.
- The product page needs one request: the product response already carries, for each
  input port, the products that produce its contract. The contract page adds one
  usage request. Nothing is fetched per port.
- The existing CI gates hold for new code: cyclomatic complexity ≤ 15 (ruff `C90`),
  coverage ≥ 80% (Python and React), mutation ≥ 70%.

---

## Approaches

| | Approach | Trade-off | Outcome |
|---|---|---|---|
| 1 | **Relational, like the contract.** Scalar columns and JSONB on `catalog.data_products`, a ports table, composite foreign key to `catalog.contract_versions`, `to_odps` builds the document | Each new ODPS field needs a migration; the database enforces rule 3 and lineage queries are joins | **Chosen** |
| 2 | Whole ODPS document in one JSONB column, validated against the JSON Schema on write, with a few extracted columns | Any ODPS field round-trips untouched, but contract references have no foreign key and lineage queries run inside JSON | Rejected |
| — | Reuse `platform.data_ports`, `data_ports_type`, `product_port_binding` | They model ports shared between products through a binding table; ODPS ports belong to one product, keyed by name and version | Discarded |
| — | Products as ODPS YAML in Git, synced like contracts | Creating a product becomes a pull request, against the UI/UX goal; the owner scoped ODPS as an export | Discarded |

---

## Standard Notes

Facts about ODPS `v1.1.0` this design relies on, read from the Bitol site, the
examples and `schema/odps-json-schema-v1.1.0.json`.

- **Required by the JSON Schema:** top level `apiVersion`, `kind`, `id`; input and
  output port `name`; management port `name`, `content`; `inputContracts[]` `id`,
  `version`; `support[]` `channel`, `url`; `team.members[]` `username`;
  `customProperties[]` `property`, `value`; `authoritativeDefinitions[]` `type`,
  `url`; `synonyms[]` `synonym`; context `verifiedStatements[]` `question`,
  `constraints[]` `constraint`. `additionalProperties: false` at the top level and on
  most definitions.
- **`version` on a port** is "Version of the data contract associated to this output
  port, becomes the version of the output port". The schema adds that "the
  combination of the name and version is the key". The examples list the same name
  twice with two versions.
- **`contractId`** is not defined as the ODCS `id`, but the examples use UUIDs and
  ODPS points to "the ODCS data contract linked from the input port". The platform's
  ODCS `id` is the contract UUID (`to_odcs`), so `contractId` is that UUID.
- **Where ODPS places fields:** `synonyms` on the product and on output ports only
  ("tools MUST NOT accept it at other locations"); `context` on the product and on
  output ports (input ports defer to the contract's context); `description`,
  `type`, `sbom`, `inputContracts` on output ports only; `deprecated` on the
  product and on every port kind.

**Conflicts between prose and schema, and the call taken (stricter wins):**

| Topic | Prose | JSON Schema | Platform |
|---|---|---|---|
| At least one output port | Required | No `minItems` | Enforced (rule 1) |
| Product `status` | "Valid values are" the five | `examples` only | Enforced, five values |
| `customProperties[]` `property`/`value` | Optional | Required | Required |
| `managementPorts[].content` | `discoverability`, `observability`, `control` | Examples add `dictionary` | Free text; the UI suggests all four (the prose example uses `dictionary`) |
| `managementPorts[].type` | `rest` or `topic`, default `rest` | Examples | Enforced, `rest` or `topic`, default `rest` |
| Product `type` | Common values, "organizations may define custom types" | No enum | Free text; the UI suggests `sourceAligned`, `aggregate`, `consumerAligned` |
| `synonyms[].status`, `source` | Examples | — | Free text |

---

## Target Data Model

All tables live in `catalog`. JSONB columns default to `'[]'` or `'{}'` and are never
`NULL`. Column names are snake_case; the export maps them to ODPS camelCase.

### `catalog.data_products` (changed)

| Column | ODPS field | Plan |
|---|---|---|
| `id` (existing) | `id` | — |
| `name` (existing) | `name` | — |
| `domain_id UUID NOT NULL → catalog.domains(id)` | `domain` (the domain's name) | 1 |
| `status TEXT NOT NULL DEFAULT 'draft'`, check on the five values | `status`; also derives `deprecated` | 1 |
| `version TEXT NULL` | `version` (free text; the UI suggests semver) | 2 |
| `type TEXT NULL` | `type` | 2 |
| `tenant TEXT NULL` | `tenant` | 2 |
| `description JSONB` with `purpose`, `limitations`, `usage`, `authoritativeDefinitions`, `customProperties` (replaces the text column; the old text becomes `purpose`) | `description` | 2 |
| `tags`, `synonyms`, `context`, `team`, `support`, `custom_properties`, `authoritative_definitions` (JSONB) | same names | 2 |
| `created_at` (existing) | `productCreatedTs` (UTC, ISO 8601) | 3 (export) |
| `repo_url` (existing) | not exported (platform-only) | — |
| `data_contracts_id` | removed | 1 nullable, 2 dropped |

`team` and `support` reuse the structure the contract already stores
(`catalog.data_contracts.team_members`, `support`), since ODPS takes both from ODCS.

### `catalog.data_product_ports` (new, Plan 1)

One row per input or output port.

| Column | Notes |
|---|---|
| `id UUID PK` | Exported as the port `id` |
| `data_product_id UUID NOT NULL → data_products(id) ON DELETE CASCADE` | |
| `role TEXT NOT NULL`, check `input` / `output` | |
| `name TEXT NOT NULL` | |
| `version TEXT NULL` | With a contract, it **is** the contract version |
| `contract_id UUID NULL` | `FOREIGN KEY (contract_id, version) REFERENCES catalog.contract_versions(contract_id, version)`. Postgres skips the check when `contract_id` is `NULL` (MATCH SIMPLE), so a port without contract keeps a free version. A check requires `version` when `contract_id` is set |
| `type TEXT NULL`, `description TEXT NULL` | Output only (check) |
| `deprecated BOOLEAN NOT NULL DEFAULT false` | |
| `authoritative_definitions JSONB` | Plan 1: an external source's link lives here |
| `input_contracts JSONB` | Output only (check): `[{contract_id, version}]`, ODPS `inputContracts`. Plan 1. The aggregate checks each entry is one of the product's own input ports with a contract (designer call 1), so the entry inherits that port's foreign key and needs none of its own |
| `tags`, `custom_properties` (JSONB) | Plan 2 |
| `synonyms`, `context`, `sbom` (JSONB) | Plan 2, output only (check) |
| `created_at`, `updated_at` | |

- **Key:** `UNIQUE NULLS NOT DISTINCT (data_product_id, role, name, version)`
  (Postgres 15+; local and Azure run 16).
- **Deleting a contract a port uses fails**, because the cascade from
  `data_contracts` to `contract_versions` hits the port's `RESTRICT`. Today a product
  blocks the delete the same way. The contract delete route maps the violation to
  `409` with the number of ports using it.
- Indexes: `(data_product_id)` and `(contract_id, version)`.

### `catalog.data_product_management_ports` (new, Plan 2)

`id`, `data_product_id` (cascade), `name NOT NULL`, `content NOT NULL`,
`type NOT NULL DEFAULT 'rest'` (check `rest`/`topic`), `url`, `channel`,
`description`, `deprecated`, `tags`, `custom_properties`,
`authoritative_definitions`. Key: `UNIQUE (data_product_id, name)`.

### Removed

`platform.data_ports`, `platform.data_ports_type` and `platform.product_port_binding`
(Plan 1), and `platform.control_ports`, `platform.control_port_types` (Plan 2, replaced
by management ports). No code reads them. Each migration checks the tables are empty
and stops with a clear error if not. `governance.resource_type` keeps `DATA_PORT`;
nothing grants on it today.

---

## Rules and Where They Live

One owner per rule (see [Engineering Principles](#engineering-principles)).

| Rule | Owner | How |
|---|---|---|
| 1. At least one output port | Aggregate | `DataProduct` cannot be built or saved without an output port. Ports are only written with their product, so no other path can remove the last one |
| 2. Contract optional on outputs | Data model | Nullable `contract_id` |
| 3. Input contract and version exist | Database | Composite foreign key to `contract_versions`; the repository turns the violation into an error naming the contract and version |
| 4. Input never on a `retired` contract | Use case | One query for the status of every referenced contract; `deprecated` returns a warning |
| `inputContracts` cite own inputs with a contract | Aggregate | In memory |
| Output-only fields (`type`, `description`, `input_contracts`, …) | Database | Check constraint on `role`, translated by the repository |
| Port key unique | Database | Unique key, translated by the repository |
| `retired` product is terminal | Aggregate | The status change is a method on `DataProduct` that refuses to leave `retired` |

**Contracts without a version row.** Contracts created before the version history
(#35) have no `contract_versions` row for their current version until they change.
Every write that attaches a contract to a port first calls the existing
`add_baseline_version` for the contract's current version, a no-op when the row
exists, so picking any contract works.

---

## API

Ports are part of the product payload: `POST /data-products` and
`PUT /data-products/{id}` take the full lists, the response returns them. A `PUT`
replaces the lists, matching existing rows by `(role, name, version)` so they keep
their `id` (designer call 6).

```jsonc
// POST /data-products (Plan 1 shape)
{
  "name": "Risco de Crédito",
  "description": "…",              // Plan 2 turns this into { purpose, usage, limitations }
  "domain_id": "…",
  "status": "draft",
  "output_ports": [
    { "name": "exposicao-credito", "type": "tables", "description": "…",
      "contract_id": "…", "version": "1.0.0",   // version defaults to the contract's current one
      "input_contracts": [{ "contract_id": "…", "version": "2.1.0" }] },
    { "name": "alerta-limite", "type": "topic" }  // no contract: not consumable
  ],
  "input_ports": [
    { "name": "cadastro_clientes", "contract_id": "…", "version": "2.1.0" },
    { "name": "core-bancario-operacoes",
      "authoritative_definitions": [{ "type": "implementation", "url": "https://…" }] }
  ]
}
```

- The response adds, on each input port with a contract, `produced_by`: the products
  whose output ports carry that contract version (id, name, status), read in the same
  query as the ports.
- `data_contracts_id` leaves the request and response in Plan 1. The frontend
  changes in the same plan; nothing else calls these routes.
- Validation errors are `422` with one message per broken rule, written for a person:
  "A data product needs at least one output", "Version 3.0.0 of contract
  *Cadastro de Clientes* does not exist".
- Warnings (deprecated input contract, contract already produced elsewhere, output
  contract from another domain) come back in a `warnings` list on a successful write.
- **`GET /data-contracts/{id}/ports`** (Plan 1) lists every port that references the
  contract, with product id, name, domain, status, role, port name and version. It
  feeds the contract's "Produced by / Consumed by" panel and the product's upstream
  view.
- **`GET /data-products/{id}/odps`** (Plan 3) returns the ODPS YAML.
- The GitHub repository name (`dp-<domain>-<product>`) and README scaffold read the
  product's own domain instead of its contract's.

---

## UI/UX

### Principles (every plan)

- **Short path first.** Creating a product asks for name, domain, description and one
  output. Everything else has a sensible default or sits in a collapsed "More ODPS
  fields" section.
- **The platform fills what it knows.** New products start as `draft`; the domain is
  preselected when the user belongs to one; picking a contract fills the port's name
  (from the contract title) and version (its current one); an input picked from a
  contract shows which product produces it.
- **Rules explained where they bite**, inline, in plain language, before submit.
  The rule 1 message sits on the Outputs section, not in a toast.
- **Show consequences, offer the fix.** An output without contract carries a
  "Not consumable" badge with "Add a contract"; a pinned version behind the latest
  shows "v1.1.0 available" with a one-click action; a deprecated input contract is
  flagged on the consumer's page.
- **Lineage where people already look:** the product page shows inputs → product →
  outputs; the contract page shows who produces and consumes it; the marketplace
  filters by domain and status.
- **Reuse the design system:** `ContractPicker`, `EditableRows`, `TeamMembers`,
  `SupportChannels`, `StatusGlyph`, `DomainChip`, `Badge`, `Modal`. No new visual
  language.
- **Accessible and tested:** every control labelled and keyboard reachable; each new
  component ships with tests (React coverage gate 80%, mutation 70%).

### Screens (text sketches, to refine in each plan)

Product form (Plan 1; Plan 2 adds the collapsed section):

```
New data product
Name         [Risco de Crédito          ]
Domain       [Risco ▾]      Status [Draft ▾]
Description  [...]

Outputs · at least one                              [+ Add output]
  exposicao-credito   tables   Exposição de Crédito · v1.0.0 · active
  alerta-limite       topic    No contract — not consumable  [Add a contract]

Inputs                                [+ From a contract] [+ External source]
  cadastro_clientes   Cadastro de Clientes · v2.1.0 · produced by Cadastro PF
  core-bancario       External source · wiki link

▸ More ODPS fields (version, type, team, support, tags, context, …)
                                            [Cancel] [Create product]
```

Product page lineage strip (Plan 1):

```
 INPUTS                         PRODUCT                  OUTPUTS
 cadastro_clientes v2.1.0 ─┐                        ┌─ exposicao-credito v1.0.0
   by Cadastro PF          ├─► Risco de Crédito  ───┤    2 consumers
 core-bancario (external) ─┘   Active · Risco       └─ alerta-limite (no contract)
```

Contract page usage panel (Plan 1):

```
Usage
Produced by   Risco de Crédito · exposicao-credito · v1.0.0
Consumed by   Cobrança · exposicao · v1.0.0
              Provisões · exposicao · v0.9.0  ⚠ pinned to an older version
```

Version moves (designer calls 5 and 9): when a contract gains a version, the
producer's output port shows "v1.1.0 available → Publish" and the consumer's input
shows "v1.1.0 available → Switch". Both add a port row with the new version (ODPS
keys ports by name and version); Publish also offers to mark the old output
deprecated, and a MAJOR move asks for confirmation. A row nothing uses any more shows
"Remove". The form groups rows of the same name, newest first, so two versions read
as one port in transition rather than two ports.

Contract pickers (designer call 10): the output picker and the domain list keep
today's membership filter; the input picker lists every contract and shows each
one's domain and producing product.

---

## Plans

Execution order. A later plan may assume every earlier one has shipped.

| # | Plan file (`docs/superpowers/plans/`) | Delivers | Schema change |
|---|---|---|---|
| 1 | `2026-11-24-odps-1-ports-status-domain.md` | Input/output ports, `inputContracts`, status, domain on the product, rules 1–4, contract usage endpoint, existing products migrated; product form, product page lineage, contract usage panel, marketplace filters | Additive, plus backfill; `data_contracts_id` becomes nullable |
| 2 | `2026-11-24-odps-2-product-metadata.md` | Every other ODPS field: `version`, `type`, `tenant`, structured `description`, `tags`, `synonyms`, `context`, `team`, `support`, `customProperties`, `authoritativeDefinitions`; port `tags`, `customProperties`, `synonyms`, `context`, `sbom`; management ports; variables kept verbatim; `data_contracts_id` and `platform.control_*` dropped; "More ODPS fields" section and management ports editor | Additive, then drops |
| 3 | `2026-11-24-odps-3-export.md` | `to_odps`, `GET /data-products/{id}/odps`, JSON Schema validation in unit tests and CI, "Export ODPS" (view and download) on the product page | None |

Migration versions are `2026112400000N`, N the plan number: Plan 1 uses
`20261124000001`, Plan 2 `20261124000002` (and `20261124000003` if it needs a second
file; Plan 3 has no migration).

### Plan 1 — Ports, status, domain

- Migration: add `domain_id` (backfilled from each product's contract, then
  `NOT NULL`), `status` (existing rows `active`), the ports table; make
  `data_contracts_id` nullable; drop the three `platform` data-port tables.
- **Backfill (designer call 3).** SQL cannot write a contract version snapshot, which
  holds YAML. An idempotent command runs in `entrypoint.sh` after the migrations: for
  each product whose `data_contracts_id` is set, it ensures the baseline version row,
  creates the output port (name from the contract title, slugified; version the
  contract's current one; type `tables`), and clears `data_contracts_id`, one product
  per transaction. It is a no-op once done, and it runs before the app serves, so no
  request loads a product that has no output port yet.
- Domain entities and use cases for ports, the rules table above, `422` messages and
  `warnings`.
- `GET /data-contracts/{id}/ports`; contract delete maps the port violation to `409`.
- Repository naming and scaffold use the product's domain.
- UI: the form, the lineage strip, the usage panel, marketplace domain and status
  filters and status badge, version-move actions.

### Plan 2 — Every other ODPS field

- **Release gate (designer call 11):** ship only after a release containing Plan 1
  is deployed everywhere, including local databases (start the stack once on Plan 1).
- Migration: the remaining product and port columns, `description` from text to
  JSONB (`{"purpose": <old text>, "usage": "", "limitations": ""}`), management ports
  table, drop `data_contracts_id` (stops with a clear error while any row still has
  it set), drop `platform.control_*` (empty check). Plan 1's backfill command and its
  `entrypoint.sh` line are deleted in the same plan.
- Strings may hold `${VAR}` or `${VAR:-default}`; validation accepts them and nothing
  substitutes them.
- UI: the "More ODPS fields" section, grouped as *About* (version, type, tenant,
  tags, synonyms), *People* (team, support), *For AI agents* (context: instructions,
  constraints, verified statements), *Links* (authoritative definitions, custom
  properties), and *Management ports*. Output ports gain the same where ODPS allows
  them, plus SBOM links. Each group shows a one-line explanation of what the field is
  for, since most users have not read ODPS.

### Plan 3 — Export

- `backend/use_cases/data_product/odps.py`: `ODPS_API_VERSION = "v1.1.0"`,
  `to_odps(product, ports, management_ports, domain_name) -> dict`, pure, no I/O,
  omitting empty sections, as `to_odcs` does. `contractId` is the contract UUID;
  `inputContracts[].id` likewise. `deprecated` is derived (designer call 7).
  `repo_url` is not exported (anti-goal); an implementation link may go in
  `authoritativeDefinitions` only if the owner adds it by hand.
- Unit tests validate `to_odps` output against the official schema, vendored verbatim
  at `tests/fixtures/odps/odps-json-schema-v1.1.0.json` from the `v1.1.0` tag (record
  its SHA-256 in the plan, as the ODCS plan did), and check the prose rules the
  schema does not (rule 1, status values).
- CI validates the export of a product built by the real code, in the job that
  already lints ODCS. There is no ODPS CLI; validation is `jsonschema`.
- UI: "Export ODPS" on the product page opens the YAML with copy and download.

---

## Validation

- Backend: `.venv\Scripts\python.exe -m pytest tests/ -q`, including migration tests
  against Docker Postgres (rules enforced by the database are tested there, not only
  in use cases).
- Frontend, from `frontend/`: `npm test`, `npm run lint`, `npm run build`.
- Each plan ends with the product created end to end in the browser against a local
  stack: a product with two outputs (one without contract), one contract input and
  one external input; then the contract page showing its usage.

## Repository Rules

- Branch from `develop`; PRs target `develop`; releases squash-merge into `main`.
- Commit messages and PR text carry no Claude or Claude Code attribution of any kind.
- `git commit` needs `.venv\Scripts` prefixed to `PATH`, or pre-commit fails.
- Lint with `ruff check backend`. Passing test paths makes ruff rewrite those files.
- Migrations are SQL in `database/migrations/`; regenerate `atlas.sum` from LF content
  with the `arigaio/atlas` Docker image (`atlas` is not on `PATH`).
- Layering stays as it is: entities and pure logic hold no I/O, routers orchestrate
  GitHub calls, and GitHub failures stay warn-only.

## Left to the Builder

- Component boundaries in the frontend, and whether the form is one page or a
  short stepper, as long as the short path above holds.
- The exact wording of messages and badges, in English like the rest of the UI.
