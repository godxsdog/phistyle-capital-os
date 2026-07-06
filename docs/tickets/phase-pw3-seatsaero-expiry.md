# Ticket: Phase PW-3 — seats.aero Integration + Expiry Agent

FABLE-APPROVED: yes (2026-07-06, written at session close).
PRE-START: fresh-context Sonnet clarity review recommended (user may
waive; record it). IMPLEMENTATION OWNER: Codex. VERDICT: new Fable
session. DEPENDS ON: PW-2 ACCEPTED.
Binding spec: docs/strategy/point-wallet-master-spec.md.

## 2. USER VALUE

Watched routes auto-pull award availability from seats.aero into
award_quotes (feeding the PW-2 engine); daily expiry checks surface
90/60/30/7-day warnings on the dashboard.

## 3. DECISIONS ALREADY MADE

- seats.aero Partner API only; SEATS_AERO_API_KEY env var (user's Pro
  subscription); Codex reads current API docs at implementation, cites
  them in the report; tier/shape mismatch = STOP (expiry agent still
  ships).
- Watches: origin, destination, cabin, date range, program NULL=any.
  Fetch on explicit trigger + Mac mini cron line (same pattern as the
  Phase 17 design: documented crontab entry invoking a compose exec
  command). Snapshots append-only; idempotent per (watch, seen_date).
- A snapshot can be promoted to an award_quote with one click
  (prefills program/miles/taxes; user adds cash price) → PW-2 engine.
- Expiry agent: daily command scans accounts' expiry data; thresholds
  90/60/30/7; results persisted (expiry_alerts table) and shown on
  the wallet dashboard. Notification = dashboard only in this phase
  (email/LINE later). Suggested actions are static text, not LLM.
- No LLM; no credentials beyond the API key; no booking actions.

## 5. SCOPE (one additive migration, id ≤ 32 chars)

award_watches, award_snapshots, expiry_alerts tables (columns per
master spec pattern; Codex proposes exact columns in the plan section
of its first report IF ambiguity remains — otherwise implement);
seats_aero_service (rewrite of the reverted one is allowed as
reference via git history 2acf126); fetch + expiry commands; additive
main.py routes; /wallet additions (watches CRUD, snapshots list,
promote button, expiry panel); tests with mocked HTTP (no live API in
tests), threshold edge cases, idempotent daily runs.

## 6/8. OUT OF SCOPE / MUST NOT CHANGE

Broader-than-seats.aero search (standing NO-GO); auto-booking;
email/LINE; LLM; PW-1/PW-2 core tables (only additive FKs allowed);
decision pipeline; trading tables; llm_router.

## 15. STOP

API tier mismatch; rate limits forcing architecture change; any
credential storage beyond the env key; schema beyond §5.

## 16. COMPLETION REPORT

Standard + migration pasted + API doc citations.
