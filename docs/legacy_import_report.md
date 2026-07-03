# Legacy Import Report

Date: 2026-07-03

Status: documentation only. The imported apps under `legacy/` are references and must not be refactored, integrated, or treated as active OS modules yet.

## Scope

Inspected folders:

- `legacy/points-wallet`
- `legacy/dental-ppt`

No legacy files were modified.

## Executive Summary

Two existing local apps were imported as legacy references:

- `points-wallet`: a personal points, miles, award-cost, expiry, and redemption comparison tool.
- `dental-ppt`: a clinical case presentation builder that accepts before/after dental images, searches PubMed, and generates PowerPoint files.

Both apps are useful domain references, but both are monolithic prototypes. They combine frontend, domain rules, persistence, external integrations, and local HTTPS serving inside app-specific files. They should remain untouched until the OS has app boundaries, platform services, storage rules, and permission rules in place.

## `legacy/points-wallet`

### Files

| File | Current role |
| --- | --- |
| `legacy/points-wallet/index.html` | Single-page browser UI for account balances, award-cost comparison, Ping An Wanlitong rules, official purchase costs, expiry tracking, and Seats.aero lookup controls. |
| `legacy/points-wallet/app.js` | Main client-side state, rendering, calculations, inline editing, local storage, API calls, and domain logic. |
| `legacy/points-wallet/styles.css` | Standalone app styling. |
| `legacy/points-wallet/server.py` | Local HTTPS static server plus JSON APIs for data, exchange rates, transfer rules, Ping An rules, official costs, TripPlus refresh attempt, and Seats.aero search. |
| `legacy/points-wallet/manifest.json` | PWA manifest. |
| `legacy/points-wallet/sw.js` | Simple service worker for static asset caching. |

### Current Capabilities

- Tracks points and miles balances for two owners: `kai` and `wife`.
- Supports hotel and airline program lists.
- Stores balances, per-point costs, expiry dates, quotes, transfer history, award-cost history, Ping An display presets, and Marriott cost settings.
- Uses browser `localStorage` as the primary offline cache.
- Optionally syncs local state to `data/points_wallet.json` through `/api/data`.
- Retrieves exchange rates from `open.er-api.com`, with hard-coded fallback rates.
- Maintains manual Ping An Wanlitong rules through `/api/pingan-rules`.
- Maintains manual official or promotional purchase costs through `/api/official-costs`.
- Calculates award-cost routes across manual balances, Marriott transfers, Ping An Wanlitong, and official purchase-cost sources.
- Calls a local `seat_aero` client for award availability search if that project dependency exists.
- Generates an expiry reminder mailto link for soon-to-expire balances.
- Provides PWA-style static caching for offline use.

### Notable Domain Logic

Keep as reference when designing the future Points Wallet app:

- Program taxonomy: hotel programs and airline programs.
- Account model: owner, category, program, balance, cost per point, expiry date, note.
- Award-cost route comparison:
  - direct mileage balance use;
  - Marriott transfer path;
  - promotional Marriott purchase path;
  - Ping An Wanlitong direct and Marriott-transfer formulas;
  - official or promotional mile purchase costs;
  - tax conversion into TWD.
- Marriott transfer assumptions:
  - default 3:1 transfer ratio;
  - 60k Bonvoy plus 5k miles bonus for most programs;
  - LifeMiles exception.
- Expiry window logic for 30, 60, and 180-day views.
- Seats.aero result normalization and mapping from source identifiers to program names.

### Risks and Limitations

- Business rules are embedded directly in browser rendering code.
- Data validation is minimal and mostly implicit.
- Sensitive personal-finance data is saved to browser local storage and local JSON without auth, audit, or app-scoped storage controls.
- Exchange rates have hard-coded fallback values that can become stale.
- Ping An, Marriott, and official-purchase formulas lack schema validation and versioning.
- Server paths write to project-level `data/` and `config/` folders directly.
- The local HTTPS certificate path is shared with the dental app naming, which is a platform concern rather than app logic.
- TripPlus refresh is intentionally nonfunctional or unreliable because the page does not expose a stable API.
- The service worker and manifest are app-specific prototype assets, not OS-level plugin or app registration.

### Preserve as Reference

- Domain vocabulary and workflows.
- Cost-comparison behaviors.
- Ping An Wanlitong maintenance model.
- Marriott transfer handling.
- Award search input and normalization expectations.
- Expiry reminder concept.

### Discard or Rewrite

- Rewrite the app shell and DOM rendering instead of moving `index.html` and `app.js` directly.
- Rewrite persistence around platform storage, typed schemas, migrations, and app-scoped data ownership.
- Rewrite `/api/data`, `/api/pingan-rules`, and `/api/official-costs` as app APIs backed by platform storage.
- Rewrite external integrations as services:
  - exchange rates;
  - Seats.aero;
  - email or notifications;
  - browser automation only if needed for vendors without APIs.
- Discard the TripPlus scraping stub unless a stable, permitted integration is identified.
- Discard or replace the current local HTTPS server once the OS platform has a dev/runtime server.
- Replace direct `mailto:` expiry reminders with platform notifications or email service.
- Treat `manifest.json` and `sw.js` as prototype references only.

## `legacy/dental-ppt`

### Files

| File | Current role |
| --- | --- |
| `legacy/dental-ppt/index.html` | Single-page browser UI for clinical case metadata, image uploads, PubMed search, image pair preview, and PPT generation. |
| `legacy/dental-ppt/app.js` | Client-side upload state, image compression, before/after pairing, form collection, PubMed fetch, and PPT download behavior. |
| `legacy/dental-ppt/styles.css` | Standalone app styling. |
| `legacy/dental-ppt/server.py` | Local HTTPS static server plus PubMed search, case saving, image normalization, before/after alignment, and PowerPoint generation. |

### Current Capabilities

- Collects clinical case metadata:
  - case title;
  - patient code;
  - doctor;
  - date;
  - treatment;
  - case type;
  - chief concern;
  - clinical notes;
  - comparison notes;
  - final notes.
- Accepts before/after images in three categories:
  - intraoral;
  - extraoral;
  - xray.
- Compresses uploaded images in the browser before sending them to the backend.
- Pairs before and after images by order within category.
- Searches PubMed through NCBI E-utilities.
- Saves generated case data under `data/dental_cases`.
- Normalizes images with Pillow and optional OpenCV.
- Applies category-specific image cropping and alignment:
  - eye-aligned extraoral portrait crops when possible;
  - extraoral subject bounding boxes;
  - intraoral subject bounding boxes;
  - general salient-region fallback.
- Normalizes before/after image tone and color for comparison slides.
- Generates a `.pptx` file with title, case summary, category overview, before/after comparison slides, notes, missing-category slide, and references slide.

### Notable Domain Logic

Keep as reference when designing the future Dental PPT app:

- Case metadata fields and default values.
- Image slot taxonomy: stage plus category.
- Before/after pairing by upload order.
- Browser-side image compression before upload.
- Case persistence shape: case JSON plus saved images.
- PubMed query construction from treatment, concern, clinical notes, and comparison notes.
- PubMed citation normalization.
- PPT slide structure and clinical disclaimers.
- Image normalization and comparison preparation algorithms.

### Risks and Limitations

- Medical data and patient-related artifacts are written to local project folders without platform permissions, encryption, retention rules, or audit logs.
- Patient code and clinical notes are treated as plain form fields without sensitivity controls.
- PubMed search is embedded in the app server rather than a reusable service.
- PPT generation, image processing, server routing, and static serving are all in one file.
- Image alignment algorithms are useful but need proper tests with clinical sample fixtures before reuse.
- Temporary files are created during PPT generation and are not managed by a platform artifact lifecycle.
- The app uses the same certificate file naming as Points Wallet, which should become platform runtime configuration.
- The frontend assumes a colocated backend at `/api/papers` and `/api/presentations`.

### Preserve as Reference

- Clinical workflow and case metadata.
- Image category and before/after pairing model.
- Image normalization ideas.
- PPT structure and slide generation sequence.
- PubMed search and citation output shape.

### Discard or Rewrite

- Rewrite the frontend as an OS app rather than moving the standalone HTML/CSS/JS directly.
- Rewrite the backend as separated app API plus services:
  - app-owned case workflow;
  - PubMed service;
  - document generation worker;
  - platform storage integration.
- Rewrite medical storage with sensitivity class `medical`, explicit permissions, audit logs, and retention rules.
- Rewrite PPT generation into a tested document-generation module or job.
- Keep image-processing algorithms as reference, but move them only after tests and sample-based validation.
- Replace local HTTPS server and shared cert assumptions with platform runtime configuration.
- Avoid reusing the current PubMed tool email value and hard-coded local labels.

## Cross-App Observations

### Shared Patterns

- Both apps are local-first prototypes.
- Both use a simple static frontend plus Python `http.server`.
- Both use local HTTPS redirects.
- Both assume app APIs live under the same origin.
- Both write generated or user data under project-level folders.
- Both mix domain logic and infrastructure concerns.

### Migration Implications

- Do not integrate either app directly into Capital.
- Do not move code until the OS app contract is available.
- Do not place domain rules in `shared/`.
- External API wrappers should become `services/`.
- Local file writes should route through `platform/storage`.
- Sensitive data should be classified before any dashboard or agent access.
- Agents should eventually interact through app/service APIs, not by editing JSON or generated files directly.

## Recommended Hold State

Keep both folders under `legacy/` as read-only references until these prerequisites exist:

1. App registry schema.
2. App sensitivity and permission model.
3. Platform storage model.
4. Service boundary for external integrations.
5. App API contract.
6. Test strategy for extracted domain logic.

