# App and Agent Mapping

Date: 2026-07-03

Status: planning document only. No code reads this mapping yet. These agents are
not implemented unless already noted as scaffolded.

## Purpose

PhiStyle OS separates apps from agents. Apps provide product surfaces and domain
context. Agents perform scoped work through the Agent Runtime.

## Planned Mapping

| App | Agents |
| --- | --- |
| Capital | Daily Brief Agent, News Agent, Scoring Agent, Portfolio Agent |
| Points Wallet | Points Agent |
| Dental PPT | Dental Case Agent, Evidence Agent |
| Travel | Travel Agent |
| Snowboard | Snowboard Agent |
| Shared | Echo Agent |

## Current Boundary

- Points Wallet and Dental PPT remain legacy references only.
- No legacy app code should be imported or modified for this mapping.
- No registry, runtime, backend, or frontend code should read this file until a
  later implementation phase explicitly asks for it.
- App-specific agents should be registered through the runtime later, not wired
  directly into app code.
- The Echo Agent remains the shared test agent for runtime validation.
