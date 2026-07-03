# Module Graph

Date: 2026-07-03

This graph describes intended dependency direction for PhiStyle OS. It is architecture documentation only.

## Allowed Dependency Direction

```text
apps       -> platform
apps       -> services
apps       -> shared

agents     -> apps public APIs
agents     -> platform
agents     -> services
agents     -> prompts
agents     -> workflows

platform   -> services
platform   -> shared

services   -> shared

plugins    -> platform/plugin-runtime
plugins    -> declared app/service/agent extension points
```

## Forbidden Dependency Direction

```text
shared     -> apps
shared     -> platform
shared     -> services

services   -> apps internals
platform   -> apps internals

apps/*     -> apps/* internals
agents     -> private app files
plugins    -> undeclared private data
```

## High-Level Graph

```text
                       ┌─────────────────┐
                       │     prompts     │
                       └────────┬────────┘
                                │
                                v
┌─────────────┐        ┌─────────────────┐
│  workflows  │ <────> │     agents      │
└──────┬──────┘        └───────┬─────────┘
       │                       │
       v                       v
┌─────────────────────────────────────────┐
│                  apps                   │
│ capital | points-wallet | dental | ...  │
└──────┬──────────────┬──────────────┬────┘
       │              │              │
       v              v              v
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│  platform   │  │  services   │  │   shared    │
└──────┬──────┘  └──────┬──────┘  └──────▲──────┘
       │                │                │
       └────────────────┴────────────────┘
```

## Platform Internal Graph

```text
platform/dashboard
  -> platform/auth
  -> platform/registry
  -> platform/notifications
  -> platform/jobs
  -> shared/ui
  -> shared/utils

platform/registry
  -> shared/database
  -> shared/config
  -> shared/utils

platform/auth
  -> shared/database
  -> shared/config
  -> shared/utils

platform/permissions
  -> platform/auth
  -> platform/registry
  -> shared/database

platform/notifications
  -> platform/permissions
  -> services/email
  -> shared/database
  -> shared/utils

platform/storage
  -> platform/permissions
  -> shared/database
  -> shared/config
  -> shared/utils

platform/jobs
  -> platform/registry
  -> platform/notifications
  -> platform/audit
  -> shared/database
  -> shared/utils

platform/audit
  -> shared/database
  -> shared/utils

platform/plugin-runtime
  -> platform/registry
  -> platform/permissions
  -> platform/audit
  -> shared/config
  -> shared/utils
```

## Services Graph

```text
services/llm-router
  -> shared/config
  -> shared/database
  -> shared/utils
  -> prompts

services/exchange-rate
  -> shared/config
  -> shared/database
  -> shared/utils

services/seats-aero
  -> shared/config
  -> shared/database
  -> shared/utils

services/pubmed
  -> shared/config
  -> shared/database
  -> shared/utils

services/email
  -> shared/config
  -> shared/utils

services/market-data
  -> shared/config
  -> shared/database
  -> shared/utils

services/browser-automation
  -> platform/audit
  -> shared/config
  -> shared/utils
```

## App Dependency Matrix

| App | Platform dependencies | Service dependencies | Shared dependencies |
| --- | --- | --- | --- |
| `apps/capital` | auth, permissions, notifications, storage, jobs, audit | market-data, exchange-rate, llm-router, email | database, ui, utils, config, types |
| `apps/points-wallet` | auth, permissions, notifications, storage, jobs | exchange-rate, seats-aero, email | database, ui, utils, config, types |
| `apps/dental-ppt` | auth, permissions, storage, jobs, notifications, audit | pubmed, llm-router, email | database, ui, utils, config, types |
| `apps/travel` | auth, permissions, notifications, storage, jobs | seats-aero, exchange-rate, llm-router, email | database, ui, utils, config, types |
| `apps/snowboard` | auth, notifications, storage, jobs | llm-router, email | database, ui, utils, config, types |

## Agent Dependency Matrix

| Agent | May call | Must not do |
| --- | --- | --- |
| `capital-agent` | Capital public API, market-data, exchange-rate, llm-router, jobs, notifications | read Dental files, mutate Points Wallet private data |
| `travel-agent` | Travel public API, Points Wallet public cost API, seats-aero, exchange-rate, llm-router | directly edit Points Wallet JSON |
| `medical-agent` | Dental public API, pubmed, llm-router, jobs, storage with permission | access Capital/Points Wallet private data |
| `personal-ops-agent` | registry, dashboard, jobs, notifications, app public APIs with permission | bypass permissions or write private files directly |

## Plugin Extension Points

Plugins may extend only declared extension points.

```text
plugins/*
  -> platform/plugin-runtime
  -> platform/registry registration
  -> platform/permissions policy
  -> optional app/service/agent extension point
```

Examples:

- A new travel connector registers a service adapter through `services/*`.
- A new dashboard widget registers through `platform/dashboard`.
- A new agent prompt registers through `prompts/agents`.
- A new app registers through `platform/registry`.

## Public API Rule

Cross-app communication must go through public APIs.

Good:

```text
travel-agent
  -> apps/travel API
  -> services/seats-aero
  -> apps/points-wallet public cost API
```

Bad:

```text
travel-agent
  -> apps/points-wallet/data/private.json
```

Good:

```text
medical-agent
  -> apps/dental-ppt API
  -> services/pubmed
  -> platform/storage
```

Bad:

```text
medical-agent
  -> raw dental image folder
  -> modifies files without case API
```

## Data Ownership

| Data | Owner | Shared through |
| --- | --- | --- |
| portfolio, watchlist, investment scores | `apps/capital` | Capital public API |
| points balances, loyalty cost rules | `apps/points-wallet` | Points Wallet public API |
| dental cases, images, PPTs | `apps/dental-ppt` | Dental public API with medical permission |
| app metadata | `platform/registry` | Registry API |
| jobs and schedules | `platform/jobs` | Jobs API |
| notifications | `platform/notifications` | Notifications API |
| external API cache | relevant `services/*` | Service API |
| audit logs | `platform/audit` | Audit API |

## LLM Readiness

LLM calls should pass through:

```text
agent/app
  -> services/llm-router
  -> prompts/*
  -> platform/audit
```

Every LLM output should record:

- model;
- prompt id/version;
- input summary;
- output schema;
- evidence references;
- tool calls;
- timestamp;
- requesting app/agent;
- permission context.

## Scalability Check

This graph scales if:

- apps do not import each other;
- services remain integration wrappers;
- platform remains domain-neutral;
- shared stays boring;
- agents use APIs;
- plugins declare permissions;
- audit is central.

It fails if:

- Capital becomes the parent of every app;
- dashboard reads private app data directly;
- agents edit files directly;
- shared contains domain rules;
- services accumulate UI/business workflows.

