# Workforce Expansion 2 — Reorganization, Reports, Resilience & Guides

Working agreement (unchanged):
- **Atomic commits**: each logical change = one commit (unit of work).
- **Phase push**: committed atomically as I go, pushed only at each phase end (never mid-phase).
- **Test parity**: every function added must have a test added in the same commit.
- Command convention: run suite as `.venv\Scripts\python.exe -m pytest -q`.

Milestones from user feedback (this TODO):

| Phase | Milestone | Notes |
|---|---|---|
| **D** | Remove "Notas" (changelog/version notes) feature | Routes, template, service, model, ORM mapping, repository, tests, nav link. Code-only removal is non-destructive; prod `changelog_notes` table stays (no DROP), fresh DBs stop creating it. |
| **B** | New workforce **dashboard** landing page | A new workforce home summarizing the module. Keep `/work/exec` (A7) as a deeper KPI view. |
| **C** | **HTML reports** (serverless/Linux-safe, no Excel) | Shared HTML report renderer; workforce report covering tasks/accomplishments/events/5S/ideas/kudos over scoped teams + date filter. Keep existing Excel clock report unchanged. |
| **A** | Reorganize workforce **nav into dropdowns** | Group related links into dropdowns to reduce clutter in the work navbar. |
| **E** | Per-feature **usage guide** on each page | A short onboarding guide shown on each workforce page so new users grasp each feature. |
| **F** | **Resilience** to command/leader/admin changes | Deactivation-preserving history for fired bosses; team renames keep reports/histories/decisions/approvals accessible; kill the broken FK-driven user deletion. |

---

## Phase D — Remove the Notas / changelog (version notes) feature
- [x] Remove routes `work_changelog`, `work_changelog_create`, `work_changelog_delete` from `src/entrypoints/work_routes.py`
- [x] Delete template `src/entrypoints/templates/work_changelog.html`
- [x] Delete `src/service_layer/changelog_service.py`; drop re-exports in `services.py`
- [x] Remove `ChangeLogNote` from `src/domain/model.py`, `src/adapters/orm.py`, `src/adapters/repository.py`
- [x] Remove the "Notas" nav link from `base.html`
- [x] Delete changelog tests (`tests/unit/test_changelog.py`, `TestWorkChangelog` in tests/integration/test_route_rendering.py)
- [x] Full suite green (389 passed)

## Phase B — Workforce Dashboard (new landing)
- [x] Add `/work` route + `work_dashboard.html` summarizing scoped teams (members, open tasks/ideas, accomplishments, 5S avg, kudos, recent activity, quick links)
- [x] Set `/work` (not `/work/tasks`) as the workforce landing; update `appModeWorkHome` span + switch landing
- [x] Keep `/work/exec` untouched
- [x] Tests: dashboard route renders for employee, scoped team shown, empty when no team

## Phase C — HTML Reports (serverless-safe)
- [x] Shared HTML report renderer service + template (matches styling, printable)
- [x] Workforce report route + page: scoped teams + date filter, sections for tasks/accomplishments/events/5S/ideas/kudos/wiki
- [x] Wire report into workforce nav (Reports dropdown item) + a button on dashboard
- [x] Tests: report page renders for a manager with data; scoping enforced; HTML contains expected sections

## Phase A — Workforce Nav reorganization (dropdowns)
- [x] Group: Tarefas/Conquistas/Ideias/5S under a "Atividade" dropdown; Equipes under "Estrutura"; Cultura dropdown (exists); Relatórios/Executivo under "Gestão"; Painel stays a top-level link
- [x] Keep the mode-switch; ensure dropdown items styled for dark navy navbar
- [x] Tests: nav dropdowns render expected items; no clutter regression

## Phase E — Per-feature onboarding guides
- [x] Shared guide snippet/macro (collapsible "Como funciona?" card) used on each work template
- [x] Adopt on: dashboard, tasks, accomplishments, ideas, teams, 5s, culture (wiki/mentoring/kudos/events), exec, reports
- [x] Tests: guide block present on each page (parity)

## Phase F — Resilience (deactivations, leader removal, team renames)
- [x] Add `User.active`/soft-deactivation (or replace `delete_user` with deactivate) so workforce history, decisions, approvals, audit remain intact and FK references survive
- [x] `team_service.rename` keeps history: already safe (FK by team_id); add regression test + audit record of rename
- [x] Ensure scoping works for teams with no `lead_user_id` (MANAGER resolves own team) — add tests
- [x] Report/history pages render gracefully for removed/disabled users (labels fallback) — already `.get(id,'---')`; harden + test
- [x] Full suite green

---

## Final gate
- [x] `.venv\Scripts\python.exe -m pytest -q` green (412 passed, 7 subtests)
- [x] `node --check` on touched JS (app_mode.js OK)
- [x] Update `DOCUMENTATION_EXPANSION.md`, `DOCUMENTATION.md`, `README.md` as needed (README had no workforce section)
- [x] Document per-phase in this file as each lands

*Discipline: atomic commits, test parity per commit, push only at phase end.*

---

# Workforce Expansion 3 — Kanban, Dashboard de dados, Metas e Likes

| Phase | Milestone | Status |
|---|---|---|
| **K** | **Kanban de gestão rápida** no Painel | Task statuses viram estágios do board (`backlog`, `focus_week`, `in_execution`, `pending_approval`, `waiting`, `done`, `cancelled`); drag-and-drop + fallback por select; gate de aprovação (só gestor conclui/cancela ou aprova). |
| **V** | **Dashboard de dados (gráficos)** no Painel | `dashboard_service` + Chart.js: tarefas por estágio, ideias por status, likes por time, 5S por mês. |
| **M** | **Conquistas → Metas (gamificadas)** | `target_date` + `points`; status derivado (em andamento/atingida/atrasada); placar de pontos. |
| **L** | **Kudos → Likes** | Rotas `/work/culture/likes` + labels; domínio/tabela `kudos` mantidos. |

- [x] Kanban + estágios + gate de aprovação (testes de tarefa e dashboard)
- [x] Dashboard visual com Chart.js (testes de `dashboard_metrics`)
- [x] Metas com data-alvo, pontos e placar (testes de `meta_status`/`meta_leaderboard`)
- [x] Likes (rotas + labels) — testes atualizados
- [x] Suíte verde (446 passed, 7 subtests)
