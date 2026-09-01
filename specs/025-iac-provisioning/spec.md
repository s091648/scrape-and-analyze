# Feature Specification: Infrastructure as Code for Deployment Environments

**Feature Branch**: `025-iac-provisioning`

**Created**: 2026-08-26

**Status**: Draft

> **Revision 4 (2026-08-31, "Option A")**: the Railway service *variables* left Terraform — the community `railway` provider is unusable at scale. Terraform now manages only the GitHub Actions secrets/variables; Railway vars are pushed by `scripts/push_railway_variables.py` from `railway-services.json` + `secrets/railway-*.tfvars`. See `plan.md` "Revision 4" and `quickstart.md`. FR intent unchanged.

**Input**: User description: "我需要實作一個新的 feature ，那就是實作 IaC (preferably terraform) 。我目前是把我的 app 部署在 railway 平台上面，而且會根據不同的使用情境 (PR時使用 staging: ci.yml , 正式 release 時使用 production: release.yml ) 而有不同的 environment 。目前 deploy 的工作主要都是透過 railway CLI 去做，但是環境變數的設置等等都是我自己要在 railway 平台上面手動操作，這非常的不方便。而且我之後也希望可以有其他平台部署的支援方案，所以希望能夠使用類似 terraform 這樣的 IaC 語言去構築我的 stack 。"

## Clarifications

### Session 2026-08-26

- Q: Should the IaC tooling manage secret variable *values* end-to-end (flowing from GitHub Actions secrets into the hosting platform), or only track which secret keys should exist while values continue to be applied by a separate out-of-band mechanism? → A: Manage secret values end-to-end. GitHub Actions secrets are the source of truth for the value itself and are injected into the apply step at run time; the IaC tool's own state (which necessarily contains the plaintext value once applied) MUST live in a remote, encrypted-at-rest, access-restricted backend — never committed to the repository or treated as a version-controlled file.
- Q: Should IaC scope extend to the GitHub Actions secrets/variables that CI itself reads (`secrets.*`/`vars.*` in `ci.yml`/`release.yml`), or stay limited to the hosting platform's resources with GitHub's side left manually managed? → A: Full closed loop — IaC manages both the GitHub Actions secrets/variables store and the hosting platform's resources, so there is a single declarative source of truth for both. Exactly one credential (a GitHub PAT/token scoped to manage repository secrets) is the sole exception left outside IaC's own management — it must be created and stored manually, since a credential cannot grant itself the permission to manage itself.
- Q: Railway's own managed database services (e.g. Redis/Postgres, where used by staging/production) have no clean IaC-manageable resource in the available tooling (the legacy plugin approach was deprecated in favor of database templates). What is the IaC scope for these? → A: Manual, reference-only. The database services themselves continue to be provisioned/managed manually in Railway, as today; IaC's role is limited to declaring the app-service environment variables that reference them (e.g. a variable whose value is the literal string `${{Redis.REDIS_URL}}`, which Railway resolves server-side regardless of how the referencing variable was created).

### Session 2026-08-28 (implementation revision 2)

- Q: FR-013 originally said "exactly one" standing manual credential (the GitHub PAT). Implementation shows the IaC tool authenticates to three independent systems it cannot bootstrap itself — how many standing manual credentials are there really? → A: **Three**, for the same self-management reason: (1) an HCP Terraform API token authenticating the remote *state backend*, (2) a GitHub PAT scoped to repo secrets/variables authenticating the GitHub provider, (3) an account/workspace-level Railway token authenticating the Railway provider. Each is needed *before* the apply that could manage it can run, so none can be self-managed. FR-013 is updated accordingly.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Declare deployment infrastructure as version-controlled code (Priority: P1)

As the maintainer, I want the full set of deployed services and their configuration (build settings, resource sizing, environment variables) for both the staging and production environments to be defined in version-controlled declarative files, so that provisioning a service's configuration no longer requires manually clicking through the hosting platform's dashboard, and every change to that configuration goes through the same review process as any other code change.

**Why this priority**: This is the core problem statement — manual dashboard configuration is the specific pain point called out, and it blocks everything else (repeatability, review, future portability).

**Independent Test**: Can be fully tested by taking one existing service's current dashboard configuration (e.g. one of the ten Railway services already deployed via `ci.yml`/`release.yml`), expressing it declaratively, applying it against a real Railway project, and confirming the resulting service matches what the dashboard previously showed — with zero manual dashboard edits required.

**Acceptance Scenarios**:

1. **Given** a service's configuration exists only as manual settings in the hosting dashboard, **When** the maintainer expresses that configuration in the declarative IaC files and applies them, **Then** the running service's configuration matches the declared definition and no manual dashboard step was needed.
2. **Given** the declarative files are the source of truth, **When** the maintainer changes a setting only in the files (not the dashboard) and applies, **Then** the change is reflected on the running service.
3. **Given** an apply is about to change production configuration, **When** the maintainer runs the apply step, **Then** they are shown what will change before it takes effect.

---

### User Story 2 - Manage environment variables per environment without manual dashboard edits (Priority: P1)

As the maintainer, I want to add, update, or remove an environment variable for a service in one declarative place per environment (staging, production), so that I no longer have to manually repeat the same edit across the hosting dashboard for each environment and each affected service.

**Why this priority**: Explicitly named as the most disruptive part of the current manual workflow; independently valuable even before every other piece of service config is migrated to IaC.

**Independent Test**: Can be fully tested by adding a new non-secret environment variable to the declarative definition for staging, applying it, and confirming the running staging service sees the new value — without opening the hosting dashboard.

**Acceptance Scenarios**:

1. **Given** an environment variable needs to change for staging only, **When** the maintainer updates the staging declaration and applies, **Then** only the staging service is affected and production is untouched.
2. **Given** a variable is a secret (API key, database URL), **When** it is declared and applied, **Then** its value is never written in plaintext into a version-controlled file or CI log.
3. **Given** the same variable exists in both environments with different values, **When** either environment is applied, **Then** each environment keeps its own independent value.

---

### User Story 3 - Apply infrastructure changes from the existing CI/CD pipelines (Priority: P2)

As the maintainer, I want the existing PR-time staging pipeline (`ci.yml`) and release-time production pipeline (`release.yml`) to apply the declared infrastructure automatically, so that infrastructure changes ship through the same automated flow as application code instead of a separate manual step I have to remember to run.

**Why this priority**: Delivers ongoing value (no drift between what's declared and what's running) but depends on Story 1 existing first; the pipelines can still call an IaC apply step manually/out-of-band as an interim state.

**Independent Test**: Can be fully tested by adding an infrastructure change to a PR branch and confirming `ci.yml`'s staging deploy step applies it to the shared staging environment, then confirming a tagged release applies it to production via `release.yml`.

**Acceptance Scenarios**:

1. **Given** a PR includes a declarative infrastructure change, **When** `ci.yml`'s staging deploy stage runs, **Then** the change is applied to staging as part of that same run.
2. **Given** a tagged commit is pushed, **When** `release.yml` runs, **Then** the declared production infrastructure is applied before or alongside the application deploy step.
3. **Given** an infrastructure apply fails, **When** the pipeline detects the failure, **Then** the pipeline fails loudly (matching how a failed test or failed `railway up` already fails the pipeline today) rather than silently continuing.

---

### User Story 4 - Detect configuration drift (Priority: P3)

As the maintainer, I want to be able to check whether the running infrastructure still matches the declared definition, so that an out-of-band manual change (made directly in the dashboard, deliberately or by accident) is surfaced instead of silently persisting until it causes confusion.

**Why this priority**: Valuable safety net but not required for the core workflow to already be a major improvement over today's fully manual process.

**Independent Test**: Can be fully tested by manually changing one setting directly in the hosting dashboard (bypassing IaC), then running the drift check and confirming it reports that specific setting as changed.

**Acceptance Scenarios**:

1. **Given** the declared definition and the running configuration are in sync, **When** a drift check is run, **Then** it reports no differences.
2. **Given** someone manually changed a setting directly on the hosting platform, **When** a drift check is run, **Then** it reports exactly what differs from the declaration.

---

### User Story 5 - Centralize application-side environment variable reads (Priority: P2)

As the maintainer, I want every service's own code to read each environment variable through exactly one designated module (a `config.py`/`settings.py` per Python service, a server/client-split module for the frontend) — with zero direct `os.environ`/`process.env` calls anywhere else in that service's runtime code path, including shared utility code it depends on — so that the Terraform-side inventory this feature builds (User Story 2) stays trustworthy over time instead of silently drifting out of sync with scattered, undiscoverable ad-hoc reads.

**Why this priority**: Discovered as a direct byproduct of auditing User Story 2's variable inventory against `backend/config.py`/`src/config/settings.py` — several real gaps surfaced (a shared utility reading `os.environ` directly, two "for test convenience" exceptions to the centralization rule that don't hold up for production code, and the frontend having no centralized module at all). The maintainer explicitly wants this folded into the same feature branch, since "manage environment variables" was always meant to cover both how values are supplied from outside the container (this feature's original scope) and how the running code reads them (this addition).

**Independent Test**: Can be fully tested by running a repo-wide search for direct environment-variable access outside each service's designated module and confirming zero results, then confirming each service's test suite still passes.

**Acceptance Scenarios**:

1. **Given** `src/entrypoints/cli/main.py` and `src/infrastructure/shared/observability/loki_logging.py` currently read `os.environ` directly (justified only by "tests need to see live changes, not an import-time-frozen constant"), **When** this story is complete, **Then** both call a re-readable accessor exposed by `src/config/settings.py` instead — the production code path no longer bypasses the centralized module for any reason, including test convenience.
2. **Given** `shared/utils/geoip.py` currently reads `GEOIP_DB_PATH` directly via `os.environ`, **When** this story is complete, **Then** it receives that value as an explicit parameter from the calling service's own centralized config instead of reading the environment itself.
3. **Given** the frontend currently has ~15 files calling `process.env.X` directly with no separation between server-only and client-safe values, **When** this story is complete, **Then** a server-only module (full `process.env` access, for Server Components/Route Handlers) and a client-safe module (`NEXT_PUBLIC_*` only, safe for Client Components) exist, and every existing call site is migrated to one or the other.
4. **Given** the centralization rule now applies repo-wide, **When** a new direct `os.environ`/`process.env` call is added outside a designated module, **Then** an automated check (lint rule or CI grep) catches it before merge.

---

### Edge Cases

- What happens when an apply would delete or replace a resource that is currently running in **production**? The maintainer must see this called out before it happens, not discover it after.
- How does the system prevent a secret value from ever appearing in plaintext in a version-controlled file, a pull request diff, or a CI log?
- What happens when the chosen IaC tooling cannot represent a setting the hosting platform supports (a coverage gap in the tool itself, not a mistake in the declaration)? The gap must be visible and documented, not silently dropped.
- What happens if an apply is interrupted partway (e.g. CI job cancelled, network failure)? Re-running the apply must converge to the declared state rather than leaving things in an ambiguous half-applied condition.
- What happens when the ten existing services are migrated to IaC one at a time rather than all at once — how does a partially-migrated state (some services under IaC, others still manually configured) stay safe and unambiguous about which source of truth applies to which service?
- Because IaC scope includes the GitHub Actions secrets/variables store (FR-012), a compromised or misconfigured apply now has a larger blast radius than a Railway-only tool would — it could rewrite CI credentials repo-wide. The bootstrap credentials (FR-013), especially the GitHub PAT that grants this access, must each be scoped as narrowly as the respective platform permits and never be the same token used for unrelated CI steps (e.g. the account-level Railway token used by the provider MUST be stored under a distinct secret name from the environment-scoped `RAILWAY_TOKEN` that `railway up`/`railway down` already use).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The declarative infrastructure definition MUST cover, at minimum, every app service currently deployed via `ci.yml`/`release.yml` (dashboard-backend, dashboard-frontend, storybook, scrape-and-analyze, chatbot-plugin, fastembed, weekly-report, refresh-metrics, rag-backfill, dedup-reconcile) for both the staging and production environments. This does not include Railway's own managed database services, which are out of scope per FR-014.
- **FR-002**: The system MUST allow a maintainer to create, update, or remove a service's environment variable for a specific environment by editing version-controlled files and applying them, without needing to use the hosting platform's dashboard.
- **FR-003**: The system MUST keep staging and production environment variable values independent — applying a change to one environment MUST NOT affect the other.
- **FR-004**: The system MUST NOT store secret variable values (API keys, database URLs, tokens) in plaintext within any version-controlled file, pull request diff, or CI log. The IaC tool's own applied-state record (which necessarily contains plaintext secret values once a secret is applied) MUST instead be stored in a remote backend that is encrypted at rest and access-restricted to the CI/CD pipeline and maintainer — never committed to the repository.
- **FR-004a**: Secret variable values MUST continue to originate from the existing GitHub Actions secrets store and MUST be injected into the apply step at run time (not authored directly into declarative files), so GitHub Actions secrets remain the single source of truth for what a secret's value *is*, while the IaC tool is only responsible for *applying* that value to the hosting platform.
- **FR-005**: The system MUST show a preview of pending changes before they are applied, and this preview MUST be reviewable prior to any change reaching production.
- **FR-006**: The system MUST fail visibly (not silently) when an apply cannot complete, mirroring how a failed test or failed deploy step already fails the pipeline today.
- **FR-007**: The declarative definitions MUST be reviewable through the same pull-request process as application code (i.e., live in this repository, not in an external-only tool).
- **FR-008**: The system MUST support applying infrastructure changes to the shared staging environment as part of `ci.yml`'s existing PR flow, and to production as part of `release.yml`'s existing tagged-release flow.
- **FR-009**: The system MUST allow checking whether the currently running configuration matches the declared definition (drift detection) for at least the resources it manages.
- **FR-010**: The system MUST support migrating the ten existing services to the declarative definition incrementally (one or a few at a time) without requiring a single big-bang cutover, and MUST make it unambiguous, per service, whether it is currently managed by IaC or still manually configured.
- **FR-011**: Applying a change that would delete or replace a resource MUST be distinguishable in the preview (FR-005) from an additive/in-place change, so a destructive production change cannot be applied unnoticed.
- **FR-012**: The declarative infrastructure definition MUST also cover the GitHub Actions repository secrets and variables that `ci.yml`/`release.yml` read (the `secrets.*`/`vars.*` references, e.g. `RAILWAY_TOKEN`, `RAILWAY_SERVICE_ID_*`), so there is a single declarative source of truth spanning both the CI credential/config store and the hosting platform's resources.
- **FR-013**: Exactly three credentials MUST remain outside the IaC tool's own management, created and stored manually, because each authenticates a system the tool must reach *before* any apply that could manage it: (1) an HCP Terraform API token for the remote state backend, (2) a GitHub token scoped to manage repository secrets/variables for the GitHub provider, (3) an account/workspace-level Railway token for the Railway provider. The system MUST document these three as the standing manual exceptions rather than leave them implicit. (Revised 2026-08-28 from "exactly one" — see Clarifications.)
- **FR-014**: Railway's own managed database services (e.g. Redis, Postgres) MUST remain manually provisioned and managed on the hosting platform, outside this feature's declarative definition; the declarative definition's role for these is limited to declaring the app-service variables that *reference* them (e.g. a variable value that is a Railway service-reference template string), not to creating or configuring the database services themselves.
- **FR-015**: Every backend Python service (`backend/`, `chatbot-plugin/`, `fastembed/`, and the scraper's shared `src/`) MUST read every environment variable exactly once, through that service's own centralized config/settings module — no direct `os.environ` access anywhere else in that service's runtime code path, including shared utility modules it depends on.
- **FR-016**: Where a runtime need exists to read a value fresh rather than an import-time-frozen constant, the centralized config module MUST expose an explicit re-readable accessor for that purpose. A direct `os.environ` call outside the module is not an acceptable substitute for any reason, including test-observability convenience — that justification does not hold for code that ships to production.
- **FR-017**: Shared utility code (e.g. `shared/`) MUST NOT read environment variables directly, regardless of whether it is one of the specifically-named FastAPI microservices — a shared utility needing a value MUST receive it as an explicit parameter from the calling service's own centralized config, not read the environment itself.
- **FR-018**: The frontend MUST have a centralized environment module analogous to the Python services' `config.py`, split into a server-only module (full `process.env` access, for Server Components/Route Handlers) and a client-safe module (build-time-inlined `NEXT_PUBLIC_*` values only). Client Components MUST NOT call `process.env` directly outside the client-safe module.
- **FR-019**: An automated check (lint rule or CI grep) MUST catch a direct `os.environ`/`process.env` call added outside the designated modules, so the centralization rule (FR-015/FR-017/FR-018) doesn't silently erode over time the way it already had before this story.

### Key Entities

- **Service Definition**: A declarative description of one deployable unit (e.g. `scrape-and-analyze`, `dashboard-backend`) — its build/start configuration and its set of environment variable keys. One definition may apply differently per environment.
- **Environment**: A named deployment target (`staging`, `production`) with its own set of variable values and its own applied state, isolated from other environments.
- **Environment Variable**: A key belonging to a Service Definition within a specific Environment; either a plain config value (safe to version-control), a secret (value never version-controlled in plaintext, see FR-004/FR-004a), or a reference (a literal service-reference template string, e.g. pointing at a manually-managed database service per FR-014, which the hosting platform resolves server-side).
- **Applied State**: The record of what was last successfully applied to a given Environment, used to compute what a new apply would change and to detect drift against the actually-running configuration. Because this record necessarily contains the plaintext value of any applied secret, it is itself sensitive and MUST be stored in an encrypted-at-rest, access-restricted remote backend rather than the repository (see FR-004).
- **CI Credential Store**: The GitHub Actions repository secrets and variables that `ci.yml`/`release.yml` read (`secrets.*`/`vars.*`) — brought into the same declarative definition and Applied State as the hosting platform's resources (FR-012), except for the three bootstrap credentials (FR-013) that authenticate the IaC tool to its state backend, GitHub, and Railway respectively, and therefore cannot be self-managed.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A maintainer can provision or update a service's full configuration for an environment using only version-controlled files and a single apply step — zero manual dashboard steps required for any service already migrated to IaC.
- **SC-002**: Changing an environment variable for one environment takes one file edit plus one apply step, down from the current fully manual per-environment dashboard edit.
- **SC-003**: 100% of the ten currently-deployed services are represented in the declarative definition for both staging and production by the end of the migration.
- **SC-004**: Every infrastructure change that reaches production has a reviewable preview of its effects available before it is applied.
- **SC-005**: No secret value appears in plaintext in the repository's version history at any point during or after the migration.
- **SC-006**: Aside from the three documented bootstrap credentials, a maintainer can create, update, or remove any GitHub Actions secret/variable or hosting-platform configuration value used by `ci.yml`/`release.yml` through the same single declarative-file-plus-apply workflow, with zero direct edits in either GitHub's or the hosting platform's settings UI.
- **SC-007**: A repo-wide search for direct environment-variable access (`os.environ` in Python, `process.env` in TypeScript) outside each service's designated centralized module returns zero results.

## Assumptions

- Railway remains the only hosting platform actually provisioned by this feature; support for additional platforms in the future is a design consideration (see Key Entities' environment/service separation) but not something this feature builds or validates against a second platform.
- "Staging" and "production" refer to the two existing Railway environments already referenced by `ci.yml` (`scraper / staging`) and `release.yml` (`scraper / production`) — this feature does not introduce new environment tiers.
- The existing shared-staging-environment model (services torn down via `railway down` on merge and revived via `railway up` at the next PR's start, per `check-staging-deployments`/`close-staging.yml`) continues as-is; this feature manages *configuration* of services, not the per-PR revive/teardown lifecycle itself.
- Secret values (API keys, database URLs, tokens) continue to be sourced from the existing GitHub Actions `secrets`/`vars` store rather than being newly authored or rotated as part of this feature; per the Clarifications above, this feature *does* apply them to the hosting platform declaratively (not just track their existence), which means a remote, encrypted, access-restricted state backend is an in-scope piece of infrastructure this feature must stand up — not an optional nice-to-have.
- Terraform (or an equivalent declarative IaC tool) is the preferred implementation approach per the request; Railway currently has no first-party Terraform provider, only an actively-maintained third-party community one, whose coverage gaps (e.g. no clean resource for Railway's own managed database services, since the old plugin-based approach was deprecated in favor of database templates) are a material input to remaining scope decisions.
- Per the Clarifications above, IaC scope includes the GitHub Actions secrets/variables store as well as the hosting platform's resources; the standing manual exceptions are the three bootstrap credentials that authenticate the IaC tool to its state backend (HCP Terraform API token), GitHub (repo-secrets PAT), and Railway (account-level token) — none can be self-managed (FR-013, revised 2026-08-28).
- Railway's own managed database services (Redis, Postgres, etc., where used) remain manually provisioned outside this feature's scope (FR-014); only the app-service variables that reference them are declared.
- **Scope amendment (mid-implementation, during User Story 2's audit)**: "managing environment variables" is understood to cover both how values are supplied from outside the container (this feature's original scope) and how each service's own code reads them internally (User Story 5 / FR-015–FR-019). The maintainer explicitly asked for this to be delivered on the same feature branch rather than split into a separate spec, since the audit that surfaced these gaps was itself part of this feature's work.
