---

## 2. Project Architecture

This project follows **Clean Architecture** and **Domain-Driven Design (DDD)** principles to ensure isolation of business logic from external frameworks.

### Architectural Layers

- **Domain Layer (`src/domain/`)**: Pure Python objects, entities, and business rules.
- **Service Layer (`src/service_layer/`)**: Orchestrates use cases. It coordinates the Domain Model and Infrastructure.
- **Adapters Layer (`src/adapters/`)**: Repository pattern and SQLAlchemy ORM mapping.
- **Entrypoints (`src/entrypoints/`)**: Flask web application and forms.

### Data Flow (Request Lifecycle)

1.  **Request Arrival:** A request hits a route in `flask_app.py`.
2.  **UoW Initialization:** The entrypoint instantiates `SqlAlchemyUnitOfWork`.
3.  **Service Call:** The entrypoint calls a service function (from `services.py`), passing the `uow` and necessary data.
4.  **Business Logic Execution:** The service function coordinates Domain objects and commits changes via `uow`.
5.  **Response:** The entrypoint returns a response.

### Key Patterns
- **Unit of Work (UoW):** Manages transactions and atomicity.
- **Repository:** Provides a collection-like interface for data access.
- **Dependency Inversion:** Service layer depends on abstractions, not concrete implementations.
- **Classical Mapping:** SQLAlchemy mapping via `mapper_registry.map_imperatively()`.
