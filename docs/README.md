# Docs Index

This folder contains maintainers/agent-oriented technical documentation.

## Read in this order

1. `../AGENTS.md` — top-level handoff and invariants
2. `architecture.md` — codebase structure and flow
3. `data-model.md` — SQLite schema, migration, and data contracts
4. `commands-and-ux.md` — command behavior and embed presentation rules
5. `development-runbook.md` — local workflows and safe change process
6. `roadmap-and-known-issues.md` — known constraints and next milestones

## Scope

These docs focus on:
- Fast onboarding for new coding agents
- Preserving invariants in economy/ownership logic
- Safe refactors without changing gameplay unintentionally

## Key current topics

- Instance-based cards with per-copy generations (`G-####`)
- Burn confirmation and last-dropped default targeting
- Italy-themed embed contract (`italy_embed`, `italy_marry_embed`)
- SQLite locking strategy (`BEGIN IMMEDIATE`, lock timeout setting)
