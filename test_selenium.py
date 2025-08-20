import os
import time
import logging
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService

logging.basicConfig(filename='/var/www/agentarbitrage/test_selenium.log', level=logging.DEBUG, format='%(asctime)s %(levelname)s %(name)s %(threadName)s : %(message)s')
logging.getLogger('test').info(f"Starting test_selenium.py with PID {os.getpid()}")

try:
    profile_dir = f"/tmp/chrome-profile-{os.getpid()}-{int(time.time())}"
    os.makedirs(profile_dir, exist_ok=True)
    logging.getLogger('test').info(f"Using profile dir: {profile_dir}")
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument(f'--user-data-dir={profile_dir}')
    driver_path = "/usr/local/bin/chromedriver"
    service = ChromeService(driver_path)
    driver = webdriver.Chrome(service=service, options=options)
    logging.getLogger('test').info("Selenium driver started successfully")
    driver.quit()
    os.rmdir(profile_dir)  # Clean up
except Exception as e:
    logging.getLogger('test').error(f"Selenium failed: {str(e)}")
