# Banco de Horas - Project Documentation

## 1. Project Directives (Gemini CLI)

### Core Directives
- ALWAYS respect the existing architecture and style.
- ALWAYS perform validation (testing/linting) after changes.
- ALWAYS perform a full test suite run and verify application functionality (locally if possible) before performing any commit or push.
- NEVER push changes to the repository without explicit user authorization.
- NEVER introduce secrets into the codebase.

### OS Environment & Command Compatibility
- **Environment**: All commands are executed within a Windows PowerShell environment.
- **Commands**: ALWAYS use PowerShell-compatible syntax. AVOID bash-specific utilities unless explicitly available.

## 2. Project Structure
- `src/`: Core logic (Domain, Service Layer, Adapters, Entrypoints).
- `tests/`: Complete test suite (Unit and Integration).
- `scripts/`: Maintenance, Migrations, and Debugging scripts.
- `DOCUMENTATION_DETAILED.md`: Technical documentation of all functionalities and business rules.
- `scripts/maintenance/interactive_runner.py`: Interactive test runner for rapid debugging.

