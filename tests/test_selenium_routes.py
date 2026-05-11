import unittest
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
import threading
from src.entrypoints.flask_app import app

class TestApplicationFunctional(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app_thread = threading.Thread(target=lambda: app.run(port=5000, use_reloader=False))
        cls.app_thread.daemon = True
        cls.app_thread.start()
        time.sleep(2)

        chrome_options = Options()
        chrome_options.add_argument("--headless")
        cls.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

    @classmethod
    def tearDownClass(cls):
        cls.driver.quit()

    def test_index_route(self):
        self.driver.get("http://localhost:5000/")
        self.assertIn("Banco de Horas", self.driver.page_source)

    def test_unauthorized_management_access(self):
        self.driver.get("http://localhost:5000/management")
        self.assertIn("login", self.driver.current_url)

    def test_invalid_login_submission(self):
        self.driver.get("http://localhost:5000/login")
        self.driver.find_element(By.NAME, "email").send_keys("invalid@test.com")
        self.driver.find_element(By.NAME, "password").send_keys("wrong")
        self.driver.find_element(By.NAME, "submit").click()
        self.assertIn("E-mail ou senha inválidos", self.driver.page_source)

    def test_forgot_password_invalid_email(self):
        self.driver.get("http://localhost:5000/forgot-password")
        self.driver.find_element(By.NAME, "email").send_keys("notexisting@test.com")
        self.driver.find_element(By.TAG_NAME, "button").click()
        # Should stay on page and show confirmation flash (generic message)
        self.assertIn("Esqueci minha senha", self.driver.page_source)

if __name__ == "__main__":
    unittest.main()
