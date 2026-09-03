# Banco de Horas - Technical Documentation

## Overview
Banco de Horas is an application designed to manage employee time tracking, including scheduling, clocking, justifications, and administrative oversight.

## Architectural Layers
- **Domain Layer (`src/domain/`)**: Pure Python entities representing business objects (Users, DailyPonto, WorkSchedules).
- **Service Layer (`src/service_layer/`)**: Orchestrates use cases using the Unit of Work pattern to ensure transactional integrity.
- **Adapters Layer (`src/adapters/`)**: Repository pattern implementation using SQLAlchemy for persistence.
- **Entrypoints (`src/entrypoints/`)**: Flask application with standardized decorator-based routing.

## Key Features
- **Role-Based Access Control**: Standardized via `@manager_required` and `@admin_required` decorators.
- **Unified Error Handling**: Centralized management of exceptions via `@handle_errors`.
- **Clocking Logic**: Automated time tracking with anomaly detection based on scheduled hours.
- **Management Tools**: Manual correction, justification review, and missing log generation.

## Standardized Patterns
- **Transactions**: All service methods use the `Unit of Work` pattern, ensuring atomicity via `uow.commit()`.
- **Security**: Password hashing via `werkzeug` and session management via `Flask-Login`.
- **Exceptions**: Consistent use of `ValueError` and `PermissionError` for business logic violations, handled globally in the entrypoint.

## Deployment Notes
- Environment variables required: `DATABASE_URL`, `MAIL_SERVER`, `MAIL_PORT`, `MAIL_USERNAME`, `MAIL_PASSWORD`, `BREVO_API_KEY`.
- Database: Designed for PostgreSQL (production) and SQLite (development/staging).

## Workforce Expansion (Gestão)
The application is being extended **in place** (Option A: same site, same DB) into a workforce-management portal: internal tasks/checklists, team accomplishments with periods, an idea board, a 5S-per-sector audit, a culture module (wiki, kudos, events), team dashboards, and a navbar day/night-style "magic button" mode switch that isolates the workforce nav + corps palette from the clock experience. Team is the org unit; everyone participates; new tables are auto-created by `metadata.create_all`. See **`DOCUMENTATION_EXPANSION.md`** for the full architecture, verticals, decisions, and final objective.

### Workforce reorganization, reports & resilience
- **Landing dashboard (`/work`)** — summarizes the module over the caller's scoped teams (members, open tasks/ideas, accomplishments, kudos, avg 5S), a per-team KPI table, a recent-activity feed, and quick links. `/work/exec` remains the deeper KPI view.
- **HTML reports (`/work/reports`)** — serverless/Linux-safe period + team filter over scoped teams; sections for tasks, accomplishments, ideas, 5S audits, kudos, events and wiki, with a print-friendly export (no Excel binary generation; the clock Excel report is unchanged).
- **Nav dropdowns** — the work nav is grouped into **Atividade** (Tarefas/Conquistas/Ideias/5S), **Estrutura** (Equipes), **Cultura** (Wiki/Kudos/Eventos) and **Gestão** (Relatórios/Executivo); **Painel** stays a top-level landing link. The mode switch remains always visible when `WORKFORCE_ENABLED`.
- **Tasks as objectives** — each task is an **objective**; its checklist items are the steps to fulfil it. A progress bar shows checklist completion, and a task can only be marked **Concluída** once every checklist item is done. Finishing the last item auto-completes the task (unchecking reverts it to Em andamento). Tasks can be **linked to a scheduled event** (`team_tasks.event_id`, nullable, validated against the manager's team scope) so an objective tied to a workshop/training is visible together.
- **Mentoring removed** — the mentorship feature was removed end-to-end (routes, service, repository, model, ORM table/mapping, template, nav link, tests). The prod `mentorships` table is intentionally left untouched (no DROP); it is simply no longer mapped or exposed.
- **Per-feature guides** — every work page renders a collapsible "Como funciona?" card (`_work_guide.html`) with feature-specific usage steps.
- **Markdown wiki** — wiki article bodies are rendered as **Markdown** (`{{ body | markdown }}` in `work_culture_wiki.html`) via a `render_markdown` helper in `web_helpers.py` that renders with the Python `markdown` library and **sanitizes** the output with `bleach` (strict allow-list of tags/attributes/protocols; no raw `<script>`, inline handlers, or arbitrary attributes). The wiki listing shows only a **tweet-like snippet** per article (`{{ body | snippet }}`) with the full article behind a "Ler mais" collapse, so the page stays uncluttered. Deps `markdown==3.7` and `bleach==6.2.0` (+ `webencodings`) are pinned in `requirements.txt`. A `.prose` stylesheet block in `style.css` renders the produced HTML.
- **Resilience** — the old "Notas"/changelog feature was removed (non-destructive; the prod table is left untouched). Users are now **soft-deactivated** instead of hard-deleted, so workforce history, decisions, approvals and audit keep their FK references; deactivated users cannot log in. Scoping works for manager teams with no designated lead.
