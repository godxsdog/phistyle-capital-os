# Migration Plan: PhiStyle Capital OS to PhiStyle OS

Date: 2026-07-03

This is documentation only. Do not move code yet.

## Goal

Redesign the project from an investment-only application into a five-year Personal Operating System architecture.

Capital becomes one app:

```text
apps/capital
```

The OS platform becomes separate:

```text
platform/*
services/*
shared/*
agents/*
plugins/*
```

## Guiding Rules

1. Do not merge apps into Capital.
2. Do not merge medical data with finance or travel data.
3. Do not move working apps until public boundaries are documented.
4. Do not extract shared code until repeated usage is proven.
5. Do not let agents mutate private files directly.
6. Do not make dashboard depend on app internals.
7. Preserve local-first Mac mini operation during migration.

## Phase 0: Architecture Freeze

Purpose: create shared understanding before code movement.

Deliverables:

- `docs/repository_v2.md`
- `docs/module_graph.md`
- `docs/migration_plan.md`
- app inventory and integration analysis

Rules:

- no code moves;
- no scaffolding unless explicitly requested;
- no commits unless requested.

Exit criteria:

- repository direction accepted;
- Capital-as-app decision accepted;
- platform/services/shared boundaries accepted.

## Phase 1: Create Empty Skeleton

Purpose: make target shape visible without changing runtime behavior.

Create empty folders only after approval:

```text
apps/
platform/
services/
shared/
agents/
plugins/
prompts/
workflows/
scripts/
config/
tests/
```

Add only README placeholders and ownership notes.

Do not move current files yet.

Exit criteria:

- skeleton exists;
- current repository behavior unchanged;
- documentation points to the intended ownership of each folder.

Rollback:

- remove empty folders and placeholder docs.

## Phase 2: Define Registry Schema

Purpose: make apps discoverable without coupling them.

Create schema for:

- app id;
- app name;
- app type;
- sensitivity class;
- routes;
- health endpoint;
- service labels;
- required permissions;
- storage scopes;
- plugin extension points;
- public APIs.

Potential source concepts:

- existing App Center registry from the local apps;
- future plugin manifests.

Exit criteria:

- registry schema can represent Capital, Points Wallet, Dental, Travel, Snowboard, and plugins.
- dashboard can theoretically render app cards from registry only.

Rollback:

- keep a static app list.

## Phase 3: Platform Shell

Purpose: establish the OS shell without owning app domains.

Build or migrate concepts into:

```text
platform/dashboard
platform/registry
platform/auth
platform/permissions
platform/audit
```

Responsibilities:

- app launcher;
- app health;
- permission checks;
- audit events;
- trusted device model.

Do not:

- read app private data directly;
- implement Capital scoring in platform;
- implement Dental image logic in platform;
- implement Points Wallet cost rules in platform.

Exit criteria:

- dashboard can list apps and status through registry.
- platform can check permissions.
- platform can record audit events.

Rollback:

- keep old links/registry outside platform.

## Phase 4: Shared Config and Utilities

Purpose: reduce duplicated low-level code.

Create:

```text
shared/config
shared/utils
shared/types
shared/testing
```

Move only domain-neutral helpers:

- environment loading;
- URL config;
- date formatting;
- money formatting;
- validation primitives;
- logging primitives;
- test helpers.

Do not move:

- investment scoring;
- 平安萬里通 rules;
- Marriott transfer rules;
- dental image alignment;
- PubMed ranking logic.

Exit criteria:

- shared libraries are generic.
- no app domain logic enters shared.

Rollback:

- apps keep local helper copies temporarily.

## Phase 5: External Services

Purpose: centralize integration wrappers.

Extract by API, not by app.

Recommended order:

1. `services/exchange-rate`
2. `services/seats-aero`
3. `services/pubmed`
4. `services/email`
5. `services/market-data`
6. `services/llm-router`
7. `services/browser-automation`

Rules:

- service owns authentication, retries, cache, rate limits, and normalized responses;
- apps own interpretation of responses;
- services do not own app UI or domain decisions.

Exit criteria:

- each service has a documented input/output contract.
- existing apps can use service adapters without behavior changes.

Rollback:

- apps use their original direct integrations.

## Phase 6: App Boundaries

Purpose: make each app independently maintainable.

For each app, define:

```text
README.md
app.config.json
domain/
api/
frontend/
data-adapters/
workflows/
prompts/
tests/
```

### Capital

Owns:

- investment scoring;
- watchlists;
- portfolio;
- risk;
- reports;
- capital flow philosophy.

Depends on:

- market-data;
- exchange-rate;
- llm-router;
- notifications;
- jobs;
- storage.

### Points Wallet

Owns:

- points/miles balances;
- award cost basis;
- 平安萬里通;
- Marriott transfer rules;
- expiry rules.

Depends on:

- exchange-rate;
- seats-aero;
- notifications;
- storage.

### Dental

Owns:

- case workflow;
- image comparison pipeline;
- PPT export;
- case-specific evidence use.

Depends on:

- pubmed;
- llm-router;
- storage;
- jobs;
- notifications.

Exit criteria:

- apps expose public APIs.
- apps can be disabled independently.
- apps do not import each other internally.

Rollback:

- keep app-local monoliths while preserving public boundary docs.

## Phase 7: Plugin Runtime

Purpose: allow new apps/connectors/workflows without core rewrites.

Create:

```text
platform/plugin-runtime
plugins/manifests
plugins/installed
plugins/marketplace
```

Plugin manifest should declare:

- id;
- version;
- permissions;
- routes;
- jobs;
- services;
- prompts;
- data scopes;
- install/uninstall hooks.

Exit criteria:

- plugin can register with registry.
- permissions are validated.
- plugin actions are audited.

Rollback:

- manually register apps/services in registry.

## Phase 8: Jobs and Notifications

Purpose: make scheduled and async work reliable.

Move recurring workflows into:

```text
platform/jobs
platform/notifications
workflows/*
```

Examples:

- Capital morning report;
- Points Wallet expiry reminder;
- Travel award seat monitor;
- Dental PPT generation completion;
- PubMed evidence refresh.

Exit criteria:

- jobs have status, retry, logs, and audit trail.
- notifications route through platform.

Rollback:

- apps keep local one-off actions.

## Phase 9: Agent Layer

Purpose: make agents useful without making them dangerous.

Create:

```text
agents/capital-agent
agents/travel-agent
agents/medical-agent
agents/personal-ops-agent
```

Rules:

- agents call public APIs;
- agents use `services/llm-router`;
- agents run through permissions;
- agents write audit logs;
- agents never directly mutate private app files.

Exit criteria:

- each agent has allowed tools and output schema.
- workflows can call agents safely.

Rollback:

- keep manual workflows.

## Phase 10: Data Migration

Purpose: move from ad hoc JSON/folders to durable app-owned storage.

Target:

```text
shared/database
platform/storage
```

Process:

1. define schemas;
2. build importers;
3. copy existing data;
4. run dual-read tests;
5. switch app read path;
6. keep original data as backup;
7. switch write path;
8. archive old format only after validation.

Sensitive data rules:

- Dental medical artifacts require strict permission and audit.
- Financial data requires owner-only default access.
- Dashboard shows metadata, not private content.

Exit criteria:

- existing data is preserved;
- backups exist;
- app behavior remains equivalent.

Rollback:

- switch app back to original JSON/folder data.

## Phase 11: Remote Access and Device Model

Purpose: support phones, Windows machines, and remote access safely.

Needed platform features:

- auth;
- trusted devices;
- HTTPS certificate strategy;
- reverse proxy or tunnel policy;
- permissions;
- audit;
- backup.

Do not expose medical/finance app content remotely until these exist.

## Recommended First Implementation Milestone

After this documentation is accepted:

1. create empty target skeleton;
2. define registry schema;
3. build platform registry/dashboard shell;
4. keep existing apps independent and linked through registry;
5. extract exchange-rate service first.

This gives PhiStyle OS a real backbone while keeping working apps safe.

## Stop Condition

Stop after documentation unless explicitly asked to implement.

