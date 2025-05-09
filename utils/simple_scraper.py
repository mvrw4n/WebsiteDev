from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import requests
import logging
import time
import fitz  # PyMuPDF

logger = logging.getLogger(__name__)

# ✅ Global initialization of Selenium for reuse
selenium_driver = None
MY_BOT_USER_AGENT = "WizzyBot/1.0"

def init_selenium():
    """Initialize a single Selenium session for all pages."""
    global selenium_driver
    if selenium_driver is None:
        try:
            options = Options()
            options.add_argument("--headless")  # Invisible mode
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_experimental_option("excludeSwitches", ["enable-logging"])  # Suppress Selenium logs

            service = Service(ChromeDriverManager().install())
            selenium_driver = webdriver.Chrome(service=service, options=options)
            logger.info("Selenium initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Selenium: {str(e)}")
            raise

def close_selenium():
    """Close the Selenium session when finished."""
    global selenium_driver
    if selenium_driver:
        selenium_driver.quit()
        selenium_driver = None
        logger.info("Selenium closed successfully")

def extract_text_from_pdf(pdf_content):
    """Extract raw text from a PDF."""
    try:
        with fitz.open(stream=pdf_content, filetype="pdf") as pdf_doc:
            text = "\n".join([page.get_text() for page in pdf_doc])
        return text
    except Exception as e:
        logger.error(f"Error extracting text from PDF: {str(e)}")
        return ""

def fetch_page_content(url):
    """Scrape a webpage prioritizing Requests and using Selenium as fallback."""
    global selenium_driver
    if selenium_driver is None:
        init_selenium()

    try:
        # Check if it's a PDF and extract it without Selenium
        if url.lower().endswith(".pdf"):
            logger.info(f"PDF detected, extracting text from {url}...")
            response = requests.get(url, stream=True, timeout=10)
            if response.status_code == 200:
                return extract_text_from_pdf(response.content)
            logger.error(f"Unable to download the PDF: {url}")
            return ""

        # 1st attempt: Load with requests (much faster than Selenium)
        headers = {"User-Agent": MY_BOT_USER_AGENT}
        response = requests.get(url, headers=headers, timeout=10)

        # Check if the response is valid HTML
        if response.status_code == 200 and "text/html" in response.headers.get("Content-Type", ""):
            html_content = response.text.strip()

            # Check if the page is not empty or protected
            if len(html_content) > 500:  # Empirical: less than 500 characters = suspicious page
                logger.info(f"Success: Page loaded with requests for {url}")
                return html_content
            else:
                logger.warning(f"Page too short with requests, trying with Selenium: {url}")
        else:
            logger.warning(f"Requests failed (status: {response.status_code}), trying with Selenium.")

    except requests.RequestException as e:
        logger.error(f"Requests error for {url}: {str(e)}")

    # If requests fails, try with Selenium
    try:
        logger.info(f"Selenium activated for {url}")
        selenium_driver.get(url)

        # Wait for DOM to be completely loaded before retrieving the source
        WebDriverWait(selenium_driver, 7).until(
            lambda driver: driver.execute_script("return document.readyState") == "complete"
        )

        html_content = selenium_driver.page_source
        return html_content

    except Exception as e:
        logger.error(f"Selenium failed on {url}: {str(e)}")
        return "" 