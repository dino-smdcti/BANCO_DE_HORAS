import ast
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from flask import Flask
from flask_login import LoginManager
from src.config import ADMIN_ROLES, MANAGER_LEVEL_ROLES
from src.entrypoints.decorators import admin_required, handle_errors, manager_required, role_required


class _GuardSuite:
    """Shared setup for role-guard tests."""

    def setUp(self):
        self.app = Flask(__name__)
        self.app.config['TESTING'] = True
        self.app.secret_key = 'test'
        self.login_manager = LoginManager()
        self.login_manager.init_app(self.app)

        @self.app.route('/dashboard')
        def dashboard():
            return "Dashboard"

    def _call_decorated(self, decorator, role, authenticated=True):
        with self.app.test_request_context():
            with patch('flask_login.utils._get_user') as mock_user:
                mock_user.return_value = MagicMock(role=role, is_authenticated=authenticated)

                @decorator
                def protected_route():
                    return "Success"

                return protected_route()


class TestManagerRequired(_GuardSuite, unittest.TestCase):
    def test_allows_manager_level_roles(self):
        for role in MANAGER_LEVEL_ROLES:
            with self.subTest(role=role):
                self.assertEqual(self._call_decorated(manager_required, role), "Success")

    def test_denies_employee(self):
        result = self._call_decorated(manager_required, "employee")
        self.assertEqual(result.status_code, 302)

    def test_denies_unauthenticated(self):
        result = self._call_decorated(manager_required, "manager", authenticated=False)
        self.assertEqual(result.status_code, 302)


class TestAdminRequired(_GuardSuite, unittest.TestCase):
    def test_allows_admin_roles(self):
        for role in ADMIN_ROLES:
            with self.subTest(role=role):
                self.assertEqual(self._call_decorated(admin_required, role), "Success")

    def test_denies_manager_and_employee(self):
        for role in ("manager", "employee"):
            with self.subTest(role=role):
                result = self._call_decorated(admin_required, role)
                self.assertEqual(result.status_code, 302)


class TestRoleRequired(_GuardSuite, unittest.TestCase):
    def test_allows_only_listed_roles(self):
        self.assertEqual(self._call_decorated(role_required("admin", "gestor"), "admin"), "Success")
        self.assertEqual(self._call_decorated(role_required("admin", "gestor"), "gestor"), "Success")

    def test_denies_unlisted_roles(self):
        result = self._call_decorated(role_required("admin"), "manager")
        self.assertEqual(result.status_code, 302)


class TestDecoratorOrderingConvention(unittest.TestCase):
    """Routes must stack decorators as: @login_required -> role guard -> @handle_errors."""

    ROUTES_DIR = Path(__file__).resolve().parents[1] / "src" / "entrypoints"

    def test_stacked_decorators_follow_convention(self):
        auth = "login_required"
        guards = {"admin_required", "manager_required", "role_required"}
        errors = "handle_errors"
        violations = []

        for path in self.ROUTES_DIR.glob("*_routes.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.FunctionDef) or len(node.decorator_list) < 2:
                    continue
                names = [self._decorator_name(d) for d in node.decorator_list]
                if auth in names and any(g in names for g in guards):
                    guard_idx = names.index(next(g for g in guards if g in names))
                    if names.index(auth) > guard_idx:
                        violations.append(f"{path.name}:{node.lineno} {node.name} - @{auth} must be outermost")
                if errors in names and any(g in names for g in guards):
                    guard_idx = names.index(next(g for g in guards if g in names))
                    if guard_idx > names.index(errors):
                        violations.append(f"{path.name}:{node.lineno} {node.name} - role guard must be above @{errors}")

        self.assertEqual(violations, [])

    def _decorator_name(self, decorator):
        if isinstance(decorator, ast.Name):
            return decorator.id
        if isinstance(decorator, ast.Call):
            return self._decorator_name(decorator.func)
        return ""


class TestHandleErrors(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config['TESTING'] = True
        self.app.secret_key = 'test'
        self.login_manager = LoginManager()
        self.login_manager.init_app(self.app)

        @self.app.route('/dashboard')
        def dashboard():
            return "Dashboard"

    def test_handle_errors_catches_exception(self):
        @handle_errors
        def failing_route():
            raise ValueError("Test Error")

        with self.app.test_request_context():
            result = failing_route()
            self.assertEqual(result.status_code, 302)


if __name__ == '__main__':
    unittest.main()