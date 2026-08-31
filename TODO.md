# Banco de Horas — Improvement Plan (TODO)

Working agreement:
- **Atomic commits**: each logical change = one commit (unit of work). No unrelated changes in a single commit.
- **Phase push**: changes are committed atomically as I go, but are only **pushed at the end of each phase** (never mid-phase).
- **Test parity**: every function added must have a test added in the same commit.
- **Secure email fallback**: failed email sends must fall back to a secure (no PII/log-splash) HTML route.

Command convention: run suite as
`.venv\Scripts\python.exe -m pytest -q --ignore=tests/test_role_localization.py --ignore=tests/test_selenium_routes.py`

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
- [ ] Server-side single-use, revocable tokens (hash + user + expiry in DB; invalidate on use/change)
- [x] Distinct salts/lifetimes for invite vs reset (added `TOKEN_SALT_INVITE` + `/invite/<token>` route; invite token can no longer reset password)
- [x] Stop flashing full reset URLs with tokens in HTML (reset/invite now use email fallback page; forgot/magic use generic flash)
- [x] Tests: invite token cannot reset password; reset rejected on invite route; SECRET_KEY production gate (test_token_hygiene.py)

### 1.5 Rate limiting + enumeration
- [ ] Throttle login / forgot-password / magic-login
- [ ] Normalize magic_link_login message for nonexistent users
- [ ] Make logout a POST
- [ ] Tests: generic message for unknown user; rate limit triggers

### 1.6 Stop leaking internal errors
- [ ] Replace flash(str(e)) in handle_errors and raw excepts with generic messages; log server-side
- [ ] Guard bare strptime/int/float with parse_date/parse_time + 400 responses
- [ ] Tests: malformed input returns 400 not 500; error message is generic

## Phase 2 — Correctness bugs
- [ ] Atomicity: remove uow.commit() from log_action; single commit at with exit; remove redundant explicit commits
- [ ] Notifications: mark_notifications_as_read actually sets is_read
- [ ] Inverted lunch_start_late → lunch_start_early semantics + config constant + tests
- [ ] UniqueConstraint(user_id, entry_date) on daily_pontos + migration + IntegrityError handling
- [ ] _apply_proposed_times raises ValueError on unknown stage
- [ ] Password sentinel "!" → real password_set flow
- [ ] AbstractUnitOfWork.__exit__ raises NotImplementedError instead of silent rollback
- [ ] Tests for each fix above

## Phase 3 — Database, performance & concurrency
- [ ] Indexes migration: daily_pontos(user_id,entry_date) unique, daily_pontos(entry_date), audit_logs(user_id), audit_logs(timestamp), notifications(user_id,created_at), correction_requests(status), vacations(user_id,start_date,end_date), attestations(user_id,start_date,end_date), users(role)
- [ ] Eager-load time_entries/vacations/attestations/notifications in absence processor + dashboards (fix N+1)
- [ ] Replace day-by-day range expansion with O(1) start/end comparisons
- [ ] Replace audit-log load-and-rewrite with single bulk UPDATE
- [ ] DB-backed last-check lock for daily absence processing (replace file flag)

## Phase 4 — Portability & deployment
- [ ] ABSENCE_LAST_CHECK_FILE → DB row or env-driven path
- [ ] Vercel SQLite /tmp fallback: legal-guard/log loudly
- [ ] Automated migration runner on deploy
- [ ] Drop pandas+numpy (use openpyxl), move dev tools to requirements-dev.txt, remove librt, pin psycopg2, pin Python version

## Phase 5 — Architecture / clean-up
- [ ] Split administration.py god module (vacation/holiday/attestation/facultativo services)
- [ ] Deduplicate helpers (_ponto_for, _mandatory_holidays, _facultativo_dates, _require_user)
- [ ] Standardize role decorators + ordering convention + regression test
- [ ] Centralize date/redirect/error handling in web_helpers
- [ ] Align route vs service role semantics (GESTOR vs ADMIN); clean redundant double role-check
- [ ] Ownership/team model for IDOR (largest change; sequence last)

## Phase 6 — Tests & validation
- [ ] Tests: correction cycle, anomaly badge logic, notification lifecycle, retroactive logs, bulk-fix, permission helpers, absence E2E, duplicate clock-in
- [ ] Fix dummy assertion test_database_lifecycle.py:69
- [ ] Resolve 2 skipped Selenium files (bring selenium into dev reqs or convert to route tests; document)
- [ ] Assert Excel report content, not just nonzero bytes
- [ ] LGPD: mask CPF in Excel exports
- [ ] Final gate: full pytest + node --check on JS
