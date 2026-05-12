import unittest
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
import threading
from src.entrypoints.flask_app import app

class TestDashboardRoleBadges(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Start app in background
        cls.app_thread = threading.Thread(target=lambda: app.run(port=5001, use_reloader=False))
        cls.app_thread.daemon = True
        cls.app_thread.start()
        time.sleep(3)

        chrome_options = Options()
        chrome_options.add_argument("--headless")
        cls.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

    @classmethod
    def tearDownClass(cls):
        cls.driver.quit()

    def test_manager_dashboard_role_localization(self):
        # 1. Log in
        self.driver.get("http://localhost:5001/login")
        self.driver.find_element(By.NAME, "email").send_keys("admin@admin.com")
        self.driver.find_element(By.NAME, "password").send_keys("123456")
        self.driver.find_element(By.NAME, "submit").click()
        
        # 2. Navigate to Management Dashboard
        time.sleep(2)
        self.driver.get("http://localhost:5001/management")
        
        # 3. Verify localized strings in the manager dashboard
        self.assertIn("Secretário", self.driver.page_source)
        self.assertIn("Diretor", self.driver.page_source)
        self.assertIn("Funcionário", self.driver.page_source)

if __name__ == "__main__":
    unittest.main()
