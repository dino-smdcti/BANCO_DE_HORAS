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
  domain/model.py          → Pure dataclasses (User, DailyPonto, WorkSchedule, etc.)
  service_layer/
    services.py            → All business logic (~835 lines)
    unit_of_work.py        → Transaction management
    absence_processor.py   → Auto-absence detection
    auto_log.py            → Automatic log generation
    check_logic.py         → Consistency checks
  adapters/
    orm.py                 → SQLAlchemy classical mapping
    repository.py          → Collection-like data access
  entrypoints/
    flask_app.py           → 35+ routes with role decorators
    forms.py               → WTForms definitions
    templates/             → Jinja2 HTML templates
    static/                → CSS/JS assets
tests/                     → pytest test suite
scripts/                   → Utility scripts
migrations/                → Database migration files
```

### Data Flow

```
HTTP Request → Route (flask_app.py) → UoW → Service → Domain Objects → uow.commit()
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
