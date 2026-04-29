# Project Architecture: Banco de Horas

This project follows **Clean Architecture** and **Domain-Driven Design (DDD)** principles to ensure isolation of business logic from external frameworks.

## 1. Architectural Layers

### Domain Layer (`src/domain/`)
- **Purity:** Contains pure Python objects with zero dependencies on external libraries (SQLAlchemy, Flask, etc.).
- **Models (`model.py`):** Entities (`User`, `DailyPonto`), Value Objects (`UserProfile`), and Enums (`UserRole`, `PontoStatus`).
- **Logic:** Business rules and invariants (e.g., `worked_minutes` calculation) reside here.

### Service Layer (`src/service_layer/`)
- **Orchestration (`services.py`):** Orchestrates use cases. It coordinates the Domain Model and Infrastructure.
- **Unit of Work (`unit_of_work.py`):** Implements the UoW pattern to manage database transactions and ensure atomicity.

### Adapters Layer (`src/adapters/`)
- **Repository (`repository.py`):** Implements the Repository pattern to abstract data access.
- **ORM (`orm.py`):** Handles the mapping between Domain Models and Database Tables (using SQLAlchemy's classical mapping).

### Entrypoints (`src/entrypoints/`)
- **Web Interface (`flask_app.py`):** Flask application handling HTTP requests, authentication, and routing.
- **Forms (`forms.py`):** WTForms definitions for request validation.

---

## 2. Data Flow (Request Lifecycle)

1.  **Request Arrival:** A request hits a route in `flask_app.py`.
2.  **UoW Initialization:** The entrypoint instantiates `SqlAlchemyUnitOfWork`.
3.  **Service Call:** The entrypoint calls a service function (from `services.py`), passing the `uow` and necessary data.
4.  **Business Logic Execution:**
    - The service function starts a `with uow:` block.
    - It uses `uow.users` (the repository) to fetch domain objects.
    - It invokes methods on domain objects or executes logic using them.
    - It calls `uow.commit()` if changes need to be persisted.
5.  **Transaction Finalization:** The `uow` context manager handles session closing and rollbacks on failure.
6.  **Response:** The entrypoint returns a response (redirect, template rendering, or JSON).

---

## 3. Key Patterns & Components

- **Unit of Work (UoW):** Ensures that all operations within a service call are part of a single transaction. It also decouples the service layer from the specific ORM used.
- **Repository:** Provides a collection-like interface for accessing domain objects, hiding the complexity of SQL queries.
- **Dependency Inversion:** High-level modules (Service Layer) do not depend on low-level modules (ORM/DB). Both depend on abstractions (`AbstractUnitOfWork`, `AbstractRepository`).
- **Classical Mapping:** SQLAlchemy `start_mappers()` is used to map pure domain classes to tables without inheriting from `Base`.
