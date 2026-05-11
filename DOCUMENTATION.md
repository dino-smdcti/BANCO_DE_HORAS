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
