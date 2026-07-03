# Integration Analysis: PhiStyle Repository vs Existing Apps

Date: 2026-07-03

Source material:

- `docs/current_analysis.md` in this repository.
- `docs/app_inventory.md` from the existing SeatAero workspace.
- Existing app inventory for:
  - Points Wallet
  - Dental Case Presenter

This document is analysis only. It does not move files, change code, or define implementation tasks.

## Executive Summary

The current `phistyle-capital-os` repository is a seed project for an AI-first investment operating system. It is mostly philosophy, roadmap, role prompts, and intended stack.

The existing Points Wallet and Dental Case Presenter are already working semi-independent local apps. They contain real product behavior, local data flows, and service integrations.

The main integration risk is forcing these existing apps into the current investment-first architecture. That would blur domain boundaries and create a brittle monolith.

The better direction is:

- keep Points Wallet independent;
- keep Dental Case Presenter independent;
- treat Capital as one sibling app;
- extract reusable infrastructure into platform/services/shared only where it is genuinely cross-app;
- never merge medical, financial, travel, and investment domain logic into one app.

## Current Repository Compared With Existing Apps

### `phistyle-capital-os`

Current state:

- Seed/constitution repository.
- Investment-focused philosophy.
- No implemented backend/frontend/database/agent runtime yet.
- Strong mission around AI infrastructure, CapEx, capital flow, scoring, and daily decision workflow.
- Intended stack includes FastAPI, Next.js, PostgreSQL, Redis, Qdrant, n8n, and Open WebUI.

Core strength:

- Clear investment decision philosophy.

Core limitation:

- It does not yet have app/platform/service boundaries.

### Points Wallet

Current state:

- Working local web/PWA app.
- Tracks points, miles, balances, cost basis, expiry, award cost, and Seats.aero search.
- Has app-specific rules for 平安萬里通, Marriott transfer ratios, official purchase cost, manual cost, tax/currency conversion.

Core strength:

- Domain-specific cost basis and award redemption logic.

Core limitation:

- Current implementation mixes UI, data persistence, cost logic, and external API adapters in one app.

### Dental Case Presenter

Current state:

- Working local web app for dental case PowerPoint generation.
- Handles before/after image upload, pairing, alignment, color/tone normalization, PubMed search, and PPT export.

Core strength:

- Domain-specific clinical artifact generation and image comparison pipeline.

Core limitation:

- Current implementation mixes API server, image processing, PubMed integration, storage, and PPT layout in one server file.

## Which Modules Should Remain Independent

### Points Wallet Should Remain Independent

Keep as an independent app because its domain model is unique:

- points and miles ledger;
- account ownership for self/spouse;
- balance and cost basis tracking;
- expiry tracking;
- award redemption cost comparison;
- 平安萬里通 conversion rules;
- Marriott transfer configuration;
- official/manual purchase cost sources;
- award search result interpretation.

It should not become a Capital submodule. Points Wallet may contain financial values, but its core workflow is travel/loyalty optimization, not investment portfolio management.

Independent app boundary:

```text
apps/points-wallet
```

Public APIs it may expose later:

- get account balances;
- get configured cost basis by program;
- calculate award cost;
- list expiring balances;
- import Seats.aero result into cost comparison.

### Dental Case Presenter Should Remain Independent

Keep as an independent app because it has a medical/clinical workflow:

- case intake;
- clinical notes;
- before/after image comparison;
- X-ray handling;
- PubMed evidence support;
- PPT generation;
- artifact storage;
- medical privacy requirements.

It should never be merged into Capital or Points Wallet. Its data sensitivity and workflow are fundamentally different.

Independent app boundary:

```text
apps/dental-ppt
```

Public APIs it may expose later:

- create case;
- upload case image;
- generate presentation;
- search evidence for case;
- list generated artifacts.

### Capital Should Be Independent Too

Capital should become another app, not the platform itself.

Independent app boundary:

```text
apps/capital
```

Capital owns:

- portfolio tracking;
- watchlists;
- investment signals;
- scoring interpretation;
- risk alerts;
- daily investment reports.

Capital should consume platform/services, but not own them.

## Which Modules Should Become Platform Services

Platform services are OS-level capabilities shared by apps. They are not app-specific business logic.

### App Registry

Source today:

- App Center registry concept from existing app inventory.
- Current `phistyle-capital-os` lacks app registry.

Should become:

```text
platform/registry
```

Responsibilities:

- app id, name, URL, status, data path;
- service labels and health checks;
- sensitivity class;
- permissions;
- owner/device visibility;
- app lifecycle metadata.

Consumers:

- dashboard;
- jobs;
- agents;
- notifications;
- app launcher.

### Dashboard / Launcher

Source today:

- App Center concept in existing apps.

Should become:

```text
platform/dashboard
```

Responsibilities:

- OS home screen;
- app launcher;
- service health overview;
- recent jobs;
- notification summary;
- links into independent apps.

Must not import app internals.

### Auth / Permissions

Source today:

- Missing in both repositories.

Should become:

```text
platform/auth
```

Responsibilities:

- owner identity;
- trusted devices;
- app-level access;
- sensitivity-based permissions;
- session and token policy.

Important because Dental is medical data and Points Wallet/Capital contain financial data.

### Notifications

Source today:

- Points Wallet expiry mailto concept.
- Capital roadmap LINE alert.
- Dental future export completion alerts.

Should become:

```text
platform/notifications
```

Responsibilities:

- reminder rules;
- alert routing;
- email/LINE/Telegram channel dispatch;
- quiet hours;
- severity levels;
- delivery log.

Apps submit notification events; the platform decides how to deliver them.

### Jobs

Source today:

- Capital roadmap daily workflow schedule.
- Dental PPT generation can become long-running.
- Points Wallet award search/expiry reminders can be scheduled.

Should become:

```text
platform/jobs
```

Responsibilities:

- scheduled runs;
- retries;
- job logs;
- background task status;
- recurring searches;
- daily reports.

Examples:

- Capital 07:00 daily ingestion.
- Points Wallet award seat monitor.
- Dental PPT generation job.
- PubMed evidence refresh.

### Storage

Source today:

- Points Wallet JSON files.
- Dental `data/dental_cases`.
- Capital future reports/events.

Should become:

```text
platform/storage
```

Responsibilities:

- app-scoped artifact storage;
- backup/export;
- sensitivity labels;
- retention rules;
- medical/finance isolation;
- path policy.

Storage policy belongs to platform. App domain schema belongs to the app.

## Which Modules Should Become Services

Services wrap external APIs and reusable integrations. They can be used by apps, agents, and platform jobs.

### Exchange Rate

Source today:

- Points Wallet server fetches `open.er-api.com`.

Should become:

```text
services/exchange-rate
```

Consumers:

- Points Wallet;
- Capital;
- Travel;
- possibly Snowboard travel budgeting.

Keep generic:

- currency conversion;
- rate cache;
- fallback rates;
- timestamped source metadata.

Do not embed Points Wallet-specific cost rules here.

### Seats.aero

Source today:

- Points Wallet calls Seats.aero through existing project code.

Should become:

```text
services/seats-aero
```

Consumers:

- Points Wallet;
- Travel;
- Travel Agent.

Responsibilities:

- API authentication;
- search normalization;
- cabin/tax/seat parsing;
- availability cache;
- rate limiting;
- error handling.

Do not embed Points Wallet cost-basis logic here.

### PubMed

Source today:

- Dental Case Presenter searches PubMed directly.

Should become:

```text
services/pubmed
```

Consumers:

- Dental Case Presenter;
- Medical Agent.

Responsibilities:

- PubMed search;
- result normalization;
- citation formatting;
- relevance metadata;
- evidence ranking later.

Do not embed Dental PPT layout logic here.

### Email

Source today:

- Points Wallet uses mailto concept.
- Capital roadmap wants LINE alert, not email yet.
- Dental may eventually send generated decks.

Should become:

```text
services/email
```

Consumers:

- platform notifications;
- explicit export/send actions.

Apps should normally call `platform/notifications`, not `services/email` directly.

### LLM Router

Source today:

- Current repository has prompts and model routing rules.
- Existing apps may need LLM support for travel reasoning and medical evidence summaries.

Should become:

```text
services/llm-router
```

Responsibilities:

- model routing;
- prompt selection;
- tool permissions;
- prompt versioning;
- output validation;
- audit metadata.

This should support agents without mixing agent prompts into app code.

## Which Modules Should Become Shared Libraries

Shared libraries should be low-level, boring, and domain-neutral. They should not contain app-specific business logic.

### Shared Database

Target:

```text
shared/database
```

Use for:

- database connection;
- migrations framework;
- transaction helpers;
- common base models;
- audit metadata helpers.

Do not place Points Wallet conversion rules or Dental case logic here.

### Shared UI

Target:

```text
shared/ui
```

Use for:

- design tokens;
- layout primitives;
- form controls;
- tables;
- cards;
- empty/loading/error states;
- dashboard shell components.

Do not force Points Wallet, Dental, and Capital into identical information density. Shared UI should provide primitives, not dictate product workflow.

### Shared Utils

Target:

```text
shared/utils
```

Use for:

- date formatting;
- number formatting;
- money formatting;
- JSON helpers;
- validation helpers;
- logging helpers;
- safe filename helpers;
- retry/backoff helpers.

Do not include:

- Marriott transfer rules;
- 平安萬里通 conversion rules;
- dental image alignment;
- investment scoring.

### Shared Config

Target:

```text
shared/config
```

Use for:

- environment loading;
- runtime profiles;
- secret references;
- local/network URL config;
- service endpoint config.

Secrets themselves should not be stored in docs or committed source.

## Which Modules Should Never Be Merged

### Dental Medical Data Must Never Merge With Capital Or Points Wallet

Never merge:

- dental case records;
- patient identifiers;
- intraoral/extraoral/X-ray images;
- generated PPT files;
- medical notes;
- PubMed evidence tied to a patient case.

Reason:

- medical data requires stricter privacy, access control, audit, and retention rules.

Allowed interaction:

- Medical Agent may use Dental public APIs and PubMed service.
- Platform dashboard may show app health and job status, not patient content by default.

### Points Wallet Domain Logic Must Never Merge Into Capital

Never merge:

- points/miles balances;
- award cost rules;
- 平安萬里通 conversion tables;
- Marriott transfer rules;
- official mileage purchase cost tables;
- Seats.aero result cost interpretation.

Reason:

- Points Wallet is a travel/loyalty optimization app, not an investment app.

Allowed interaction:

- Travel app can ask Points Wallet for public cost basis.
- Capital should not consume Points Wallet internals.

### Capital Investment Scoring Must Never Merge Into Platform

Never merge:

- CapEx scoring;
- investment signal ranking;
- portfolio risk;
- watchlist logic;
- Bull/Neutral/Bear scoring;
- earnings transcript investment interpretation.

Reason:

- These are Capital app domain rules, not OS platform rules.

Allowed interaction:

- Capital can use platform jobs, notifications, storage, and LLM router.
- Platform can display Capital app status, not own Capital strategy.

### External API Wrappers Must Not Merge Into App UI

Never merge long-term:

- exchange-rate fetching inside Points Wallet UI;
- Seats.aero client inside Points Wallet UI;
- PubMed client inside Dental UI;
- email delivery inside individual app screens.

Reason:

- integrations need secrets, retries, rate limits, caching, logs, and error policy.

### Agents Must Not Merge Into App State Files

Never allow agents to directly mutate:

- Points Wallet JSON files;
- Dental case folders;
- future Capital database records;
- registry files.

Agents should call public APIs or workflow endpoints, preserving validation and audit trail.

## Recommended Integration Boundaries

```text
apps/
  capital/          investment app
  points-wallet/    points and award-cost app
  dental-ppt/       clinical presentation app
  travel/           travel planning app

platform/
  auth/
  registry/
  dashboard/
  notifications/
  storage/
  jobs/

services/
  exchange-rate/
  seats-aero/
  pubmed/
  email/
  llm-router/

shared/
  database/
  ui/
  utils/
  config/

agents/
  capital-agent/
  travel-agent/
  medical-agent/
```

## Integration Priority

### Priority 1: Preserve Existing App Independence

Before any code move:

- document Points Wallet public API boundary;
- document Dental public API boundary;
- document Capital app boundary;
- tag sensitivity classes.

### Priority 2: Promote App Center Concepts To Platform

Move conceptually, not immediately:

- registry;
- dashboard;
- health checks;
- service logs;
- restart controls.

This gives PhiStyle OS a shell without merging app internals.

### Priority 3: Extract Services By External API

Extract in this order:

1. `services/exchange-rate`
2. `services/seats-aero`
3. `services/pubmed`
4. `services/email`
5. `services/llm-router`

This order reduces duplicate integration code without changing app workflows first.

### Priority 4: Create Shared Libraries Carefully

Start with:

- config;
- utils;
- UI primitives;
- database connection.

Avoid placing domain rules into shared libraries.

### Priority 5: Add Agents Last

Agents should come after app/service APIs exist. Otherwise they will become file-editing scripts instead of reliable workflow actors.

## Main Architecture Risk

The biggest risk is confusing “shared” with “centralized.”

Shared infrastructure should be centralized. Domain intelligence should not.

Correct:

- centralized exchange-rate service;
- centralized app registry;
- centralized notification delivery;
- independent Points Wallet cost rules;
- independent Dental image pipeline;
- independent Capital scoring logic.

Incorrect:

- one giant backend owning all domain logic;
- one dashboard that directly reads all app private data;
- agents directly editing JSON and image folders;
- Capital app becoming the parent of all apps.

## Conclusion

The current `phistyle-capital-os` repository provides a strong investment philosophy but no implemented architecture yet. Points Wallet and Dental Case Presenter provide real working app behavior but need clearer boundaries.

The right integration path is not to merge the apps. It is to build PhiStyle OS as a platform where:

- Capital is one app;
- Points Wallet is one app;
- Dental Case Presenter is one app;
- shared integrations become services;
- OS concerns become platform modules;
- low-level helpers become shared libraries;
- agents operate through public APIs and workflows.

