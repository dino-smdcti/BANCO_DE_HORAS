# Banco de Horas — Improvement Plan (TODO)

Working agreement:
- **Atomic commits**: each logical change = one commit (unit of work). No unrelated changes in a single commit.
- **Phase push**: changes are committed atomically as I go, but are only **pushed at the end of each phase** (never mid-phase).
- **Test parity**: every function added must have a test added in the same commit.
- **Secure email fallback**: failed email sends must fall back to a secure (no PII/log-splash) HTML route.

Command convention: run suite as
`.venv\Scripts\python.exe -m pytest -q`

---

## Phase 0 — Baseline & safety ✅
- [x] Confirm baseline tests green (92 passed)
- [x] Commit the existing verified config-refactor working tree as the foundation baseline
- [x] Create TODO.md

## Phase 1 — Critical security fixes
### 1.1 Purge tracked DB backup (remove + scrub history)
- [x] `git rm --cached banco_de_horas.db.bak`; add `*.db`, `*.db.bak`, `*.sqlite*` to `.gitignore`
- [ ] Scrub history with `git filter-repo` (remove blob from all commits), then force-push (commit 373904f, scrub deferred to phase push)
- [ ] Rotate `SECRET_KEY` + Neon DB password after scrub
- [x] Add test: assert no `*.db`/`*.db.bak` files are tracked

### 1.2 CSRF everywhere
- [x] Register `CSRFProtect(app)` in flask_app
- [x] Add hidden token to every unprotected POST form (clock, profile, magic-login, forgot, reset, admin_settings, all manager/admin forms, base delete-ponto)
- [x] Send `X-CSRFToken` on all JS fetch POSTs (main.js markRead, manager_dashboard changeUserRole, view_employee_logs saveManagerNote)
- [x] Tests: CSRF token required on state-changing routes; POST without token rejected (test_csrf_protection.py)

### 1.3 Fix privilege escalation in change_user_role
- [x] Restrict change_user_role to ROLE_ADMIN (match promote/demote)
- [x] Tests: manager/gestor cannot change roles or promote to admin (test_role_escalation.py)

### 1.3b Secure HTML email fallback (working-agreement item)
- [x] Fall back to a secure HTML page (managers/admins only) when SMTP fails (reset + invite paths)
- [x] Stop printing recipient/PII + raw SMTP errors to stderr
- [x] Tests: manager sees fallback on failed email; employee never does (test_email_fallback.py)

### 1.4 Secret key + token hygiene
- [x] Remove "dev-secret-key" fallback; raise in production when unset (`_resolve_secret_key`, tested)
- [x] Server-side single-use, revocable tokens (DB `auth_tokens` table: sha256 hash + user + kind + expiry; burned on use and revoked on password change; `token_service`, `AuthToken` model, migration `create_auth_tokens_table.py`, `uow.tokens`)
- [x] Distinct kinds/lifetimes for invite vs reset (`TOKEN_KIND_INVITE`/`TOKEN_KIND_RESET` + `/invite/<token>` route; invite token can no longer reset password)
- [x] Stop flashing full reset URLs with tokens in HTML (reset/invite now use email fallback page; forgot/magic use generic flash)
- [x] Tests: invite token cannot reset password; reset rejected on invite route; SECRET_KEY production gate (test_token_hygiene.py)

### 1.5 Rate limiting + enumeration ✅
- [x] Throttle login / forgot-password / magic-login (DB-backed `rate_limit_entries`, shared per-IP budget)
- [x] Normalize magic_link_login message for nonexistent users
- [x] Make logout a POST (with CSRF)
- [x] Tests: generic message for unknown user; rate limit triggers

### 1.6 Stop leaking internal errors
- [ ] Replace flash(str(e)) in handle_errors and raw excepts with generic messages; log server-side
- [ ] Guard bare strptime/int/float with parse_date/parse_time + 400 responses
- [ ] Tests: malformed input returns 400 not 500; error message is generic

## Phase 2 — Correctness bugs
- [x] Atomicity: remove uow.commit() from log_action; single commit at with exit; remove redundant explicit commits
- [x] Notifications: mark_notifications_as_read actually sets is_read
- [x] Inverted lunch_start_late → lunch_start_early semantics + config constant + tests
- [x] UniqueConstraint(user_id, entry_date) on daily_pontos + migration + IntegrityError handling
- [x] _apply_proposed_times raises ValueError on unknown stage
- [x] Password sentinel "!" → real password_set flow
- [x] AbstractUnitOfWork.__exit__ raises NotImplementedError instead of silent rollback
- [x] Tests for each fix above

## Phase 3 — Database, performance & concurrency
- [x] Indexes migration: daily_pontos(user_id,entry_date) unique, daily_pontos(entry_date), audit_logs(user_id), audit_logs(timestamp), notifications(user_id,created_at), correction_requests(status), vacations(user_id,start_date,end_date), attestations(user_id,start_date,end_date), users(role)
- [x] Eager-load time_entries/vacations/attestations/notifications in absence processor + dashboards (fix N+1)
- [x] Replace day-by-day range expansion with O(1) start/end comparisons
- [x] Replace audit-log load-and-rewrite with single bulk UPDATE
- [x] DB-backed last-check lock for daily absence processing (replace file flag)

## Phase 4 — Portability & deployment
- [x] ABSENCE_LAST_CHECK_FILE → DB row or env-driven path
- [x] Vercel SQLite /tmp fallback: legal-guard/log loudly
- [x] Automated migration runner on deploy
- [x] Drop pandas+numpy (use openpyxl), move dev tools to requirements-dev.txt, remove librt, pin psycopg2, pin Python version

## Phase 5 — Architecture / clean-up
- [x] Split administration.py god module (vacation/holiday/attestation/facultativo services)
- [x] Deduplicate helpers (_ponto_for, _mandatory_holidays, _facultativo_dates, _require_user)
- [x] Standardize role decorators + ordering convention + regression test
- [x] Centralize date/redirect/error handling in web_helpers
- [x] Align route vs service role semantics (GESTOR vs ADMIN); clean redundant double role-check
- [x] Ownership/team model for IDOR (largest change; sequence last)

## Phase 6 — Tests & validation ✅
- [x] Tests: correction cycle, anomaly badge logic, notification lifecycle, retroactive logs, bulk-fix, permission helpers, absence E2E, duplicate clock-in
- [x] Fix dummy assertion test_database_lifecycle.py:69
- [x] Resolve 2 skipped Selenium files (convert to route tests; no longer ignored in suite)
- [x] Assert Excel report content, not just nonzero bytes
- [x] LGPD: mask CPF in Excel exports
- [x] Final gate: full pytest + node --check on JS (258 passed, 7 subtests)

## Phase 7 — Post-hardening follow-ups
- [ ] Audit all POST routes in employee_routes/manager_routes/admin_routes for the "success path returns None -> 500" pattern (only update_note fixed so far) and add return redirects
- [x] Hotfix /management 500 (missing DATE_FORMAT import) — committed a27906f, pushed
- [x] Hotfix /update-note 500 (success returned None) — committed 9863dac, pushed

### Clock-in/out hardening (committed e7a04db, pushed)
- [x] `_register_stage` auto-creates the day's ponto for ANY explicit stage (no "Registro de chegada não encontrado" on partial/out-of-order days)
- [x] `_emit_ponto(user, today)` so later-stage-first POST doesn't fabricate a `0:00` arrival; removed dead `_require_ponto`
- [x] Keep auto-path guard: `_next_stage` still raises "Jornada completa" when all 4 stages filled + no explicit stage (pinned by test)
- [x] Frontend `main.js` MANAGEMENT_ROLES now includes `gestor`
- [x] `tests/unit/test_clock_all_scenarios.py` (9 tests)

### Geolocation made optional (committed 8e68d04, pushed)
- [x] Confirm button enabled regardless of location; only the <15-min duplicate gate can block
- [x] `main.js` `updateConfirmState()` no longer takes a location arg
- [x] Kept the "Jornada Completa" hard block (disabled button, no new clock-ins on full journal) as user requested

---

# Workforce / Gestão Expansion — Option A (in place)

Decision set (confirmed): same site + same DB; Team is the org unit (no Department entity); everyone participates; manager/admin/gestor scoping via `ensure_managed_user`; tables auto-created by `metadata.create_all` in `scripts/run_migrations.py` (no ALTER needed for new tables); `services.py` facade re-export; nav gated by `MANAGEMENT_ROLES`/`ADMIN_ROLES`; plain-HTML forms + `csrf_token()`; auditoria `record_action` + notificações `add_notification`.

Full design: see `DOCUMENTATION_EXPANSION.md`.

## Phase F0 — Shared assignment/scope foundation
- [x] `managed_team_ids(uow, actor)` (write/create scope) + `scoped_team_ids(uow, actor)` (read scope: ADMIN/GESTOR all; MANAGER own team; EMPLOYEE own team read)
- [x] Tests: `tests/unit/test_assignment_base.py` (11)
- [x] NOTE: `Team.lead_user_id` added in Phase D — idempotent Postgres ALTER in `apply_migrations.py`; fresh DBs get it via `metadata.create_all`.

## Phase A — Tasks & internal checklists
- [x] Models `TeamTask` + `TaskChecklistItem` (base de assignment)
- [x] Service + `services.py` re-export; `uow.tasks` via repository methods (add_task/list/update/delete + checklist)
- [x] Routes `/work/tasks/*` (`@manager_required` create/edit/delete; `@login_required` self-status/assignee) + nav link "Tarefas"
- [x] Templates extend base.html (`work_tasks.html`)
- [x] Tests: `tests/unit/test_tasks.py` (11) + `tests/integration/test_route_rendering.py::TestWorkTasks` (3)

## Phase B — Accomplishments with periods
- [x] Model `Accomplishment` (team_id, period, optional end_date = in-progress)
- [x] Service + routes `/work/accomplishments/*` + templates
- [x] Tests: period validation, team scoping, overlap guard

## Phase C — Idea board / KAIZEN (brainstorming)
- [x] Models `Idea` (`category` idea/kaizen) + `IdeaVote` (UNIQUE(idea_id, voter_id)); statuses open→under_review→implemented/declined (KAIZEN us-a `implemented`); optional review_date/review_owner (PDCA cadence)
- [x] Service + routes `/work/ideas/*` (anyone posts/votes; managers set status) + templates
- [x] Notify author on status change
- [x] Tests: post, unique vote, vote toggle, status transitions incl. `implemented`, kaizen category filter

## Phase D — Team dashboards (management expansion)
- [x] Add `Team.lead_user_id` (optional team lead): domain + orm `teams` column for fresh DBs (`create_all`) + **idempotent Postgres ALTER in `apply_migrations.py`** for existing prod (verify on staging first, per runbook)
- [x] Extend dashboard roll-ups from `management_panel()`/`teams.html`: members, open tasks, open ideas, accomplishments/period (feeds A7)
- [x] Rename team + lead assignment
- [x] Routes `/work/teams/*`; employees view own team read-only
- [x] Tests: lead assignment, rollup counts, manager-scoped dashboard data

## Phase B-extra — 5S por setor (filosofia de trabalho)
- [x] Models `S5Audit` (`team_id`, `auditor_id`, `date`, `total_items`, `passed_items`, `score`, `notes`) + `S5Item` default per section; reuse Vertical A infra where possible
- [x] Service + routes `/work/5s/*` (managers/auditors create; all view own-team score; monthly history) + templates
- [x] Tests: audit creation, score calc, team scoping, history

## Phase C-extra — Cultura colaborativa (Wiki, Mentoria, Kudos, Eventos)
- [ ] `WikiArticle` (`/work/culture/wiki`) — anyone writes/edits in scope
- [ ] `Mentorship` (`/work/culture/mentoring`) — 1:1 mentor/mentee, managers create
- [ ] `Kudos` (`/work/culture/kudos`) — peer recognition feed, anyone gives
- [ ] `TeamEvent` (`/work/culture/events`) — internal calendar/workshops + notifications
- [ ] Tests: CRUD per entity + scope + audit

## Phase A7 — Dashboard executivo de Indicadores (KPIs)
- [ ] Cross-team aggregation: members/task, open tasks, ideas implemented, accomplishments/period, avg 5S score, kudos
- [ ] Routes `/work/exec/*`; ADMIN/GESTOR all, MANAGER own team, EMPLOYEE read-only own team
- [ ] Tests: aggregation correctness by scope; coherent sources

## Phase W — "Magic button" mode switch
- [ ] Second palette in `style.css` under `[data-app-mode="work"]` (overrides brand custom properties)
- [ ] Auto-detect: clock pages = `clock` mode; `/work/*` pages = `work` mode
- [ ] Toggle/back button (floating or navbar) persisting choice (cookie/localStorage); JS clean `node --check`
- [ ] Apply `data-app-mode="work"` root on workforce templates + nav separation
- [ ] Gate behind env flag `WORKFORCE_ENABLED` (false default) for soft-launch/instant rollback

## Phase A6 — Patch notes / release board interno (last, droppable)
- [ ] Model `ChangeLogNote` (`version_or_date`, `title`, `description`, `category` feature/fix/config, `created_by`, `created_at`)
- [ ] Routes `/work/changelog/*` (managers/admins publish; all read; in-app notification on new note)
- [ ] Tests: publish scoping, listing, notification on new note

---
*Discipline: atomic commits, test parity per commit, push only at phase end. Suite: `.venv\Scripts\python.exe -m pytest -q` (baseline 279 passed, 7 subtests).*

---

# Prod-Safety Runbook (prod=Postgres, dev=SQLite)
Per phase, before ANY prod push:
1. [ ] Suite green locally (`.venv\Scripts\python.exe -m pytest -q`) — hard gate.
2. [ ] `node --check` on touched JS.
3. [ ] Backfill: run against staging clone of prod DB, smoke-test the new `/work/*` route as admin/manager/employee.
4. [ ] Take a prod DB backup/snapshot BEFORE running `run_migrations.py`.
5. [ ] Deploy zero-downtime: push phase → `run_migrations.py` on prod (Postgres) → smoke-test live.
6. [ ] Confirm additions are table-new/additive only; no ALTER on existing tables, no new index on pre-existing tables, `services.py` append-only.
