import unittest
from unittest.mock import MagicMock, patch
from flask import Flask, session
from flask_login import LoginManager
from src.entrypoints.decorators import manager_required, admin_required, handle_errors

class TestDecorators(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config['TESTING'] = True
        self.app.secret_key = 'test'
        self.login_manager = LoginManager()
        self.login_manager.init_app(self.app)
        
        @self.app.route('/dashboard')
        def dashboard():
            return "Dashboard"
        
    def test_manager_required_denies_access(self):
        with self.app.test_request_context():
            with patch('flask_login.utils._get_user') as mock_user:
                mock_user.return_value = MagicMock(role='employee', is_authenticated=True)
                
                @manager_required
                def protected_route():
                    return "Success"
                
                result = protected_route()
                self.assertEqual(result.status_code, 302)

    def test_handle_errors_catches_value_error(self):
        @handle_errors
        def failing_route():
            raise ValueError("Test Error")
            
        with self.app.test_request_context():
            result = failing_route()
            self.assertEqual(result.status_code, 302)
