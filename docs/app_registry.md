# App Registry

Date: 2026-07-03

Status: OS registry scaffold only. No auth, agent runtime, investment logic, or legacy integration has been implemented.

## Purpose

The App Registry is the OS-level source of truth for which apps exist, who owns their data, and how the platform can discover them.

It lets the dashboard and future platform services list apps without importing app internals.

The Python package is named `phistyle_platform.registry` to avoid conflicting with Python's standard-library `platform` module. Documentation may still refer to the OS "platform layer" as an architecture concept.

## Metadata Fields

| Field | Purpose |
| --- | --- |
| `id` | Stable app identifier. |
| `name` | User-facing app name. |
| `category` | Broad app category. |
| `status` | Current lifecycle status. |
| `sensitivity` | Data sensitivity class. |
| `route` | Future frontend route. |
| `health_endpoint` | Future app health endpoint. |
| `owner` | Owning app/module path. |
| `data_scope` | Human-readable summary of owned data. |

## Initial Apps

| App | Status | Notes |
| --- | --- | --- |
| `capital` | `scaffold` | Future investment app. No investment logic in registry. |
| `points-wallet` | `future` | Registered only as future app. Legacy code is not imported. |
| `dental-ppt` | `future` | Registered only as future medical app. Legacy code is not imported. |
| `travel` | `future` | Future travel operations app. |
| `snowboard` | `future` | Future personal app. |

## Backend API

```text
GET /apps
```

Returns the static registry entries as JSON.

## Rules

- The registry may know app metadata.
- The registry must not import app internals.
- Future apps can be registered before implementation.
- Sensitive app contents must not appear in registry responses.
- Auth and permissions are intentionally not implemented yet.
