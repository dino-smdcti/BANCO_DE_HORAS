# Banco de Horas — Employee Time Bank System

![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.0-black?logo=flask)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-D71F00?logo=sqlalchemy&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?logo=postgresql&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-003B57?logo=sqlite&logoColor=white)
![pytest](https://img.shields.io/badge/pytest-0A9EDC?logo=pytest&logoColor=white)
![Vercel](https://img.shields.io/badge/Vercel-000000?logo=vercel&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)

A full-featured employee time bank / hour management web application with role-based access control, work schedules, clock-in/out tracking, anomaly detection, absence processing, corrections, vacation/holiday management, Excel report generation, and audit logging.

## Features

- **User Authentication** — login, registration, password recovery (email), magic link login, profile management
- **Role-Based Access Control** — 4 roles: Employee, Gestor, Manager, Admin with decorator-based permissions
- **Clock-In/Out** — 4-stage tracking (arrival, lunch start, lunch end, departure) with location data
- **Anomaly Detection** — late arrival, early lunch, late return, early departure with tolerance and review workflow
- **Work Schedules** — standard and 12x36 rotation, journey type templates
- **Absence Processing** — automatic missing-log detection with justification workflow
- **Correction Requests** — employees request corrections, managers approve/reject
- **Vacation Management** — managers add vacation periods, birthday auto-vacation
- **Holiday Calendar** — auto-seeded Brazilian holidays (2025–2035) with Easter calculation
- **Excel Reports** — formatted time reports with employee info, period filtering, signature lines
- **Audit Logging** — every action recorded with user, timestamp, details
- **Notifications** — in-app + optional email via SMTP
- **Admin Tools** — promote/demote users, bulk fix entries, manage journey types

## Tech Stack

Python, Flask, SQLAlchemy, PostgreSQL/SQLite, Flask-Login, Flask-WTF, pandas, openpyxl, pytest, gunicorn, Werkzeug, smtplib

## Architecture (Clean Architecture / DDD)

```
src/
  domain/
    model.py               → Pure dataclasses (User, DailyPonto, WorkSchedule, etc.)
    time_utils.py          → Shared time arithmetic helpers
  service_layer/
    services.py            → Facade re-exporting the use-case modules below
    user_service.py        → Registration, profiles, passwords
    clock_service.py       → Clock in/out, corrections, anomaly review
    schedule_service.py    → Work schedules and journey types
    administration.py      → Company settings, start-of-analysis date
    report_service.py      → Excel report generation
    notifications.py       → In-app notifications + email
    permissions.py         → Role checks
    audit.py               → Audit logging helpers
    absence_processor.py   → Auto-absence detection (daily check state)
    unit_of_work.py        → Transaction management
  adapters/
    orm.py                 → SQLAlchemy classical mapping
    repository.py          → Collection-like data access
  entrypoints/
    flask_app.py           → App factory, login/auth infra, route registration
    auth_routes.py         → Login/logout/password/magic-link routes
    employee_routes.py     → Dashboard, clock, profile, reports
    manager_routes.py      → Management panel, corrections, schedules, journeys
    admin_routes.py        → Audit logs and company settings
    web_helpers.py         → Shared route helpers (UoW factory, date/time parsing)
    forms.py               → WTForms definitions
    templates/             → Jinja2 HTML templates
    static/                → CSS/JS assets
tests/                     → pytest test suite
scripts/                   → Utility scripts
migrations/                → Database migration files
```

### Data Flow

```
HTTP Request → Route (entrypoints/*_routes.py) → UoW → Service → Domain Objects → uow.commit()
```

### Deployment

- **Production:** Vercel (serverless) + PostgreSQL (Neon)
- **Development:** SQLite
- Environment: `DATABASE_URL`, `BREVO_API_KEY`, `MAIL_*`, `SECRET_KEY`

## Setup

```bash
pip install -r requirements.txt
python main.py
```

## License

MIT
