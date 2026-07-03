# Agent Runtime

This directory documents the platform runtime concept.

Python code lives in `phistyle_platform.runtime` to avoid conflicting with Python's standard-library `platform` module.

Current scope:

- agent registration;
- agent listing;
- manual agent execution;
- in-memory run records;
- scheduler placeholder;
- LLM Router integration point only.

No real LLM calls, background jobs, auth, investment logic, or legacy integrations are implemented.

