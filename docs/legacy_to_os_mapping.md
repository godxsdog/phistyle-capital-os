# Legacy to OS Mapping

Date: 2026-07-03

Status: documentation only. This file describes eventual ownership. It does not authorize moving or rewriting legacy code yet.

## Target Buckets

Future OS ownership follows the repository direction in `docs/repository_v2.md`:

- `apps/`: user-facing products and app-owned domain workflows.
- `services/`: reusable external integrations or isolated capability services.
- `platform/`: OS-level infrastructure shared across apps.
- `shared/`: low-level, domain-neutral types, utilities, UI primitives, config helpers, and tests.

Rule of thumb: if logic knows about points, dental images, patients, Marriott, Ping An, or award tickets, it belongs in an app domain unless it is an external integration wrapper.

## High-Level Destination

| Legacy source | Eventual destination | Notes |
| --- | --- | --- |
| `legacy/points-wallet` | `apps/points-wallet` plus supporting `services/` and `platform/` modules | Keep Points Wallet as an independent personal-finance/travel app, not part of Capital. |
| `legacy/dental-ppt` | `apps/dental-ppt` plus supporting `services/` and `platform/` modules | Treat as a medical-sensitivity app with strict permissions and storage. |

## Points Wallet Mapping

### Eventually `apps/points-wallet`

App-owned concepts:

- Points and miles account management.
- Owner-scoped account data.
- Program taxonomy for hotel and airline programs, unless later promoted into a travel-domain catalog.
- Quote history.
- Transfer history.
- Award-cost history.
- Award-cost comparison workflow.
- Ping An Wanlitong maintenance workflow.
- Official or promotional purchase-cost maintenance workflow.
- Expiry dashboard and reminder preferences.
- Seats.aero search UI and award-result application workflow.
- App-specific screens, forms, tables, and result cards.

Candidate future app structure:

```text
apps/points-wallet/
├─ README.md
├─ app.config.json
├─ domain/
│  ├─ accounts
│  ├─ award-cost
│  ├─ expiry
│  ├─ marriott-transfer
│  ├─ pingan-wanlitong
│  └─ purchase-costs
├─ api/
├─ frontend/
├─ data-adapters/
├─ workflows/
└─ tests/
```

Legacy references:

- `legacy/points-wallet/app.js`
- `legacy/points-wallet/index.html`
- `legacy/points-wallet/styles.css`

Do not copy them directly. Extract behavior deliberately after schemas and tests exist.

### Eventually `services/`

Reusable service candidates:

| Future service | Legacy reference | Reason |
| --- | --- | --- |
| `services/exchange-rate` | `server.py` `load_rates()` and client rate conversion calls | Currency conversion is reusable across travel, capital, and personal finance. |
| `services/seats-aero` | `server.py` `search_seataero()` and `app.js` result normalization | Award availability lookup is an external connector, not UI code. |
| `services/email` or platform notification delivery | `app.js` expiry mailto link | Reminder delivery should not be assembled by app DOM code. |
| `services/browser-automation` | `server.py` TripPlus refresh stub, if revived | Vendor pages without APIs should be isolated from app logic and audited. |

### Eventually `platform/`

Platform-owned capabilities:

- App registration and launch metadata for Points Wallet.
- App-scoped storage for account data, rules, histories, and backups.
- Permissions for personal-finance and travel-sensitive data.
- Audit trail for changes to balances, rules, and cost assumptions.
- Job scheduling for expiry checks and exchange-rate refreshes.
- Notification routing for expiring points.
- Runtime TLS/dev server configuration.

Potential modules:

```text
platform/registry
platform/storage
platform/permissions
platform/audit
platform/jobs
platform/notifications
```

### Eventually `shared/`

Only domain-neutral pieces should be shared:

- Date utilities such as days-until-date calculations after making them generic.
- Money and number formatting primitives after removing Points Wallet-specific labels.
- Validation helpers for dates, numbers, currency codes, and IDs.
- Generic local-first sync abstractions if used by multiple apps.
- Reusable UI primitives, not the app-specific visual design.
- Shared TypeScript or Python DTO helpers if the OS standardizes schemas.

Do not move these into `shared/`:

- Marriott transfer rules.
- Ping An Wanlitong formulas.
- Award-cost routing decisions.
- Program-specific assumptions.
- Account balance business rules.

### Discard or Rewrite

Discard or rewrite before OS integration:

- Standalone `http.server` runtime in `server.py`.
- Direct writes to project-level `data/` and `config/`.
- Browser `localStorage` as the authoritative store.
- Hard-coded exchange-rate fallback as business truth.
- TripPlus scraping stub.
- App-specific service worker and PWA manifest unless the OS later supports per-app PWAs.
- Direct mailto reminder generation.
- DOM-rendering monolith in `app.js`.

## Dental PPT Mapping

### Eventually `apps/dental-ppt`

App-owned concepts:

- Clinical case creation workflow.
- Case metadata model.
- Dental image stage and category taxonomy.
- Before/after pairing workflow.
- Case review and preview UI.
- PPT generation request workflow.
- Clinical note and disclaimer behavior.
- References selected for a case.
- Medical app configuration and sensitivity declaration.

Candidate future app structure:

```text
apps/dental-ppt/
├─ README.md
├─ app.config.json
├─ domain/
│  ├─ cases
│  ├─ image-pairing
│  ├─ presentation-outline
│  └─ references
├─ api/
├─ frontend/
├─ data-adapters/
├─ workflows/
└─ tests/
```

Legacy references:

- `legacy/dental-ppt/app.js`
- `legacy/dental-ppt/index.html`
- `legacy/dental-ppt/styles.css`
- app-facing portions of `legacy/dental-ppt/server.py`

Do not copy them directly. Medical workflow extraction should happen only with permission, storage, and audit boundaries in place.

### Eventually `services/`

Reusable service candidates:

| Future service | Legacy reference | Reason |
| --- | --- | --- |
| `services/pubmed` | `server.py` `search_pubmed()` and citation normalization | Literature search is reusable by medical agents and workflows. |
| document generation service or worker | `server.py` `build_presentation()` and slide helpers | PPT generation is a reusable artifact-generation capability, but Dental owns the clinical template. |
| image-processing worker | `server.py` normalization, cropping, eye detection, tone matching | The compute-heavy pipeline should be isolated and testable. It may remain app-private initially if no other app needs it. |

### Eventually `platform/`

Platform-owned capabilities:

- App registration and launch metadata for Dental PPT.
- Medical-sensitivity permission checks.
- App-scoped encrypted or protected storage for cases, images, and generated decks.
- Audit logs for viewing, generating, exporting, and deleting case artifacts.
- Artifact retention and cleanup.
- Background jobs for PPT generation and image processing.
- Secrets and runtime configuration for any external literature APIs.
- Runtime TLS/dev server configuration.

Potential modules:

```text
platform/registry
platform/storage
platform/permissions
platform/audit
platform/jobs
```

### Eventually `shared/`

Only domain-neutral pieces should be shared:

- Generic file upload validation.
- Generic artifact metadata types.
- Generic date and filename sanitization helpers.
- Generic form validation helpers.
- Reusable UI controls.
- Testing fixtures for file uploads and generated artifacts.

Do not move these into `shared/`:

- Dental case model.
- Dental image category taxonomy.
- Clinical slide outline.
- PubMed query defaults specific to dentistry.
- Image crop heuristics specific to intraoral, extraoral, or xray images.
- Medical disclaimers and clinical notes.

### Discard or Rewrite

Discard or rewrite before OS integration:

- Standalone `http.server` runtime in `server.py`.
- Direct writes to `data/dental_cases`.
- Shared certificate assumptions.
- Hard-coded NCBI tool and email labels.
- Browser-only state as the workflow source of truth.
- Monolithic PPT generation mixed with request handling.
- Untested image alignment and color normalization as production behavior.
- Static HTML/CSS/JS shell.

## Cross-App Shared Extraction Candidates

These are candidates only after repeated usage is proven:

| Candidate | Possible destination | Conditions |
| --- | --- | --- |
| Static app metadata | `platform/registry` | After app contract is defined. |
| App health endpoints | `platform/registry` plus app APIs | After runtime conventions exist. |
| Local file/artifact storage | `platform/storage` | Must support sensitivity classes and app scopes. |
| Background work | `platform/jobs` | Needed for PPT generation, rate refreshes, reminders, and API sync. |
| Notifications | `platform/notifications` | Needed for expiry reminders and later OS alerts. |
| Currency formatting | `shared/utils` | Only generic formatting, not app cost logic. |
| Safe filename helpers | `shared/utils` | Only if used across multiple artifact workflows. |
| UI buttons, forms, panels | `shared/ui` | Only after the frontend stack is selected. |

## Data Sensitivity Mapping

| App | Sensitivity class | Rationale |
| --- | --- | --- |
| Points Wallet | `personal-finance` with travel overlap | Contains balances, cost basis, redemption strategy, and personal travel economics. |
| Dental PPT | `medical` | Contains patient-adjacent clinical images, notes, generated decks, and references. |

Platform dashboard should not display sensitive app contents by default. It may show app name, health, and pending tasks once registry and permissions exist.

## Migration Order Recommendation

1. Keep both apps under `legacy/`.
2. Define app registry and sensitivity schema.
3. Define platform storage and audit boundaries.
4. Extract service wrappers only where external integrations are clear.
5. Rebuild app frontends against OS APIs.
6. Move domain rules with focused tests.
7. Keep legacy folders as historical references until the rebuilt apps replace their workflows.

