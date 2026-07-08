import os
from src.service_layer.services import register_user
from src.service_layer.unit_of_work import SqlAlchemyUnitOfWork

# Ensure DATABASE_URL is set in environment before running this script.

def add_gestor(email: str, password: str = "gestor123"):
    uow = SqlAlchemyUnitOfWork()
    # Register user with Gestor role
    try:
        register_user(uow, email=email, password=password, role="gestor")
        print(f"Gestor user '{email}' created successfully.")
    except Exception as e:
        print(f"Error creating Gestor user: {e}")

if __name__ == "__main__":
    # Example usage: set email via env var or replace below
    email = os.getenv("GESTOR_EMAIL", "gestor@example.com")
    add_gestor(email)
