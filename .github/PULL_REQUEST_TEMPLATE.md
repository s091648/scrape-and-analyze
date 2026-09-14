## What & Why

<!-- What does this PR change, and why? Link the issue it closes, if any. -->

## How

<!-- Brief summary of the approach. Call out any trade-offs or alternatives
you considered and rejected. -->

## Checklist

- [ ] I've read [CONTRIBUTING.md](./CONTRIBUTING.md)
- [ ] Tests added/updated for the change (or N/A, with a reason below) —
      CI (`.github/workflows/ci.yml`) runs the full unit/integration/E2E suite
      automatically on this PR, no need to run it locally first
- [ ] A new/changed Alembic migration is included if the DB schema changed
      (CI applies it to the staging DB via the `migrate` job — but only
      catches a *broken* migration, not a *missing* one, so please double-check)
- [ ] Docs updated if this changes architecture, commands, or conventions
      (`CLAUDE.md`, a service's own `README.md`, or `site/` under `specs/`)
- [ ] No secrets, API keys, or `.env*` values committed

## Screenshots / recordings

<!-- For frontend changes: before/after screenshots or a short clip. Delete
this section if not applicable. -->

## Notes for the reviewer

<!-- Anything you want a human or coderabbitai to pay extra attention to —
a risky migration, a perf-sensitive path, an intentionally-unhandled edge
case, etc. Delete if none. -->

---
<!-- coderabbitai reviews every PR automatically and may append its own
"Summary by CodeRabbit" section below this line, or post a separate
walkthrough comment — that's expected and not something you (or anyone
editing this description) need to write or remove. -->
