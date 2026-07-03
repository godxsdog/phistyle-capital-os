# Repository v2: PhiStyle Personal Operating System

Date: 2026-07-03

## Core Decision

**PhiStyle Capital OS is no longer an investment application.**

It becomes **PhiStyle OS**, a Personal Operating System. Investment is only one app inside the OS.

The repository should be designed for a five-year horizon:

- many independent apps;
- shared platform capabilities;
- reusable external services;
- plugin architecture;
- LLM-ready workflows;
- agent-ready APIs;
- local-first operation with a path to remote access later.

## Target Repository Shape

```text
phistyle-os/
├─ apps/
│  ├─ capital/
│  ├─ points-wallet/
│  ├─ dental-ppt/
│  ├─ travel/
│  ├─ snowboard/
│  └─ _template/
├─ platform/
│  ├─ auth/
│  ├─ registry/
│  ├─ dashboard/
│  ├─ notifications/
│  ├─ storage/
│  ├─ jobs/
│  ├─ permissions/
│  ├─ audit/
│  └─ plugin-runtime/
├─ services/
│  ├─ llm-router/
│  ├─ exchange-rate/
│  ├─ pubmed/
│  ├─ seats-aero/
│  ├─ email/
│  ├─ market-data/
│  └─ browser-automation/
├─ shared/
│  ├─ database/
│  ├─ ui/
│  ├─ utils/
│  ├─ config/
│  ├─ types/
│  └─ testing/
├─ agents/
│  ├─ capital-agent/
│  ├─ travel-agent/
│  ├─ medical-agent/
│  ├─ personal-ops-agent/
│  └─ _template/
├─ plugins/
│  ├─ installed/
│  ├─ manifests/
│  └─ marketplace/
├─ prompts/
│  ├─ roles/
│  ├─ agents/
│  ├─ workflows/
│  └─ evaluations/
├─ workflows/
│  ├─ daily/
│  ├─ alerts/
│  ├─ app-build/
│  └─ clinical/
├─ docs/
├─ scripts/
├─ config/
└─ tests/
```

## Top-Level Concepts

### Apps

Apps are user-facing products. They own domain workflows and domain data.

Examples:

- `apps/capital`: investment, portfolio, watchlist, risk, score, reports.
- `apps/points-wallet`: points, miles, expiry, award-cost comparison.
- `apps/dental-ppt`: clinical case presenter, image comparison, PPT generation.
- `apps/travel`: itinerary planning, award search strategy, trip operations.
- `apps/snowboard`: snowboarding trips, resort logs, gear, weather, training.

Rule: apps may consume platform and service APIs, but apps must not own platform infrastructure.

### Platform

Platform modules are OS-level capabilities shared by all apps.

- `auth`: identity, device trust, sessions.
- `registry`: app metadata, plugin metadata, health URLs, service labels.
- `dashboard`: OS home, launcher, cross-app status.
- `notifications`: reminders, alerts, delivery routing.
- `storage`: app-scoped files, artifacts, backups, retention.
- `jobs`: schedules, background tasks, retries.
- `permissions`: app and agent permission checks.
- `audit`: event history, access logs, agent actions.
- `plugin-runtime`: plugin discovery, installation, lifecycle, sandbox policy.

Rule: platform knows that apps exist, but it should not import app internals.

### Services

Services wrap external integrations or reusable capabilities.

- `llm-router`: model routing, prompt execution, tool policy, structured output.
- `exchange-rate`: currency rates and conversion.
- `pubmed`: literature search and citation normalization.
- `seats-aero`: award availability search and normalization.
- `email`: email delivery.
- `market-data`: market prices, fundamentals, filings, transcripts.
- `browser-automation`: controlled browser tasks when an official API is unavailable.

Rule: services expose stable APIs; apps and agents should not duplicate external API wrappers.

### Shared

Shared modules are low-level and domain-neutral.

- `database`: connection, migrations, transaction helpers.
- `ui`: design tokens and reusable interface primitives.
- `utils`: dates, money, validation, parsing, logging.
- `config`: environment, secrets interface, runtime profiles.
- `types`: shared DTOs and schemas.
- `testing`: test fixtures and helpers.

Rule: shared must not contain business rules from Capital, Points Wallet, Dental, Travel, or Snowboard.

### Agents

Agents are automation workers that call public APIs and workflows.

- `capital-agent`: investment analysis and report drafting.
- `travel-agent`: award search and trip planning.
- `medical-agent`: dental evidence search and case drafting.
- `personal-ops-agent`: cross-app assistant, app creation, reminders, OS operations.

Rule: agents do not mutate private files directly. They operate through app/platform/service APIs with audit logs.

### Plugins

Plugins are optional extensions. They can add apps, services, workflows, prompts, dashboards, or agent capabilities.

Each plugin should declare:

```text
plugin.json
├─ id
├─ name
├─ version
├─ type
├─ permissions
├─ routes
├─ jobs
├─ prompts
├─ services
└─ data scopes
```

Plugin types:

- app plugin;
- service plugin;
- agent plugin;
- workflow plugin;
- UI widget plugin;
- connector plugin.

Plugin runtime responsibilities:

- discover plugins;
- validate manifests;
- enforce permissions;
- register routes/jobs/prompts;
- isolate sensitive data;
- record audit events.

## App Contract

Every app should eventually follow this shape:

```text
apps/<app-id>/
├─ README.md
├─ app.config.json
├─ domain/
├─ api/
├─ frontend/
├─ data-adapters/
├─ workflows/
├─ prompts/
└─ tests/
```

Required app metadata:

- id;
- name;
- description;
- sensitivity class;
- routes;
- health endpoint;
- data ownership;
- public API surface;
- required platform permissions;
- required services.

## Sensitivity Classes

The OS should treat data differently by sensitivity.

| Class | Examples | Default access |
| --- | --- | --- |
| `medical` | Dental images, patient notes, PPTs | owner only, explicit clinical permission |
| `personal-finance` | Capital, Points Wallet costs | owner only |
| `travel` | itineraries, award searches | owner and trusted devices |
| `general` | Snowboard logs, low-risk notes | owner and trusted devices |
| `system` | registry, jobs, logs, audit | owner/admin only |

The dashboard may show app health globally, but it should not show sensitive app content unless permission allows it.

## Five-Year Scalability Principles

1. **App independence first.** Apps should be removable, replaceable, and independently testable.
2. **Platform owns cross-cutting concerns.** Auth, notifications, jobs, storage, registry, audit, and plugins belong outside apps.
3. **Services own integrations.** External APIs should not be duplicated inside app UI code.
4. **Agents use APIs.** Agents should not edit JSON files or private folders directly.
5. **Plugins are first-class.** New apps and connectors should register through manifests.
6. **Domain rules stay near the domain.** Investment scoring belongs in Capital; dental image logic belongs in Dental; award-cost rules belong in Points Wallet.
7. **LLM output must be auditable.** Prompt version, model, inputs, evidence, and output schema should be stored.
8. **Local-first, remote-ready.** Mac mini local operation remains valid, but architecture should not block secure remote access later.

## Naming

Use:

- Product/platform: `PhiStyle OS`
- Repository: `phistyle-os`
- Investment app: `apps/capital`

Avoid:

- putting `capital` in platform module names;
- making Capital the owner of the OS shell;
- storing non-investment apps under Capital.

