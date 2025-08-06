"""Browser automation for Claude.ai session key retrieval."""
import click
import time
import platform
import os
from typing import Optional


class BrowserAuth:
    """Automate session key retrieval from browser."""
    
    @staticmethod
    def get_session_key_playwright(headless: bool = False) -> Optional[str]:
        """Get session key using Playwright (cross-browser)."""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise click.ClickException(
                "Playwright not installed. Run: pip install playwright && playwright install chromium"
            )
        
        with sync_playwright() as p:
            # Launch browser
            browser = p.chromium.launch(headless=headless)
            context = browser.new_context()
            page = context.new_page()
            
            try:
                # Navigate to Claude
                page.goto("https://claude.ai", wait_until="networkidle")
                
                # Wait a moment for cookies to be set
                page.wait_for_timeout(2000)
                
                # Get cookies
                cookies = context.cookies()
                session_key = None
                
                for cookie in cookies:
                    if cookie['name'] == 'sessionKey':
                        session_key = cookie['value']
                        break
                
                if session_key and session_key.startswith("sk-ant"):
                    click.echo("✓ Found existing session key")
                    return session_key
                else:
                    if headless:
                        raise click.ClickException(
                            "Not logged in and running in headless mode. "
                            "Please run without --headless to log in interactively."
                        )
                    
                    click.echo("Not logged in to Claude.ai")
                    click.echo("Please log in in the browser window that opened...")
                    click.echo("Waiting for login (timeout: 2 minutes)...")
                    
                    # Wait for user to log in
                    for i in range(120):  # Wait up to 120 seconds
                        time.sleep(1)
                        
                        # Check for session key every second
                        cookies = context.cookies()
                        for cookie in cookies:
                            if cookie['name'] == 'sessionKey':
                                session_key = cookie['value']
                                if session_key and session_key.startswith("sk-ant"):
                                    click.echo("\n✓ Login successful!")
                                    return session_key
                        
                        # Show progress
                        if i % 10 == 0 and i > 0:
                            click.echo(f"  Still waiting... ({120 - i} seconds remaining)")
                    
                    raise click.ClickException("Login timeout - no valid session key found")
                    
            except Exception as e:
                if "net::" in str(e) or "NS_ERROR" in str(e):
                    raise click.ClickException(
                        "Failed to connect to Claude.ai. Please check your internet connection."
                    )
                raise
            finally:
                browser.close()
    
    @staticmethod
    def get_session_key_selenium() -> Optional[str]:
        """Get session key using Selenium (Chrome)."""
        try:
            from selenium import webdriver
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            from selenium.common.exceptions import TimeoutException, WebDriverException
        except ImportError:
            raise click.ClickException(
                "Selenium not installed. Run: pip install selenium"
            )
        
        # Setup Chrome options
        options = webdriver.ChromeOptions()
        options.add_experimental_option("excludeSwitches", ["enable-logging"])
        options.add_argument("--disable-blink-features=AutomationControlled")
        
        # Try to use existing Chrome profile
        profile_path = BrowserAuth._get_chrome_profile_path()
        if os.path.exists(profile_path):
            options.add_argument(f"--user-data-dir={profile_path}")
        
        try:
            driver = webdriver.Chrome(options=options)
            driver.get("https://claude.ai")
            
            # Wait for page to load
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Execute JavaScript to get sessionKey cookie
            session_key = driver.execute_script("""
                const cookies = document.cookie.split('; ');
                for (let cookie of cookies) {
                    const [name, value] = cookie.split('=');
                    if (name === 'sessionKey') {
                        return decodeURIComponent(value);
                    }
                }
                return null;
            """)
            
            if session_key and session_key.startswith("sk-ant"):
                driver.quit()
                return session_key
            else:
                click.echo("Not logged in. Please log in to Claude.ai")
                click.echo("Waiting for login... (Press Ctrl+C to cancel)")
                
                # Wait for user to log in
                for _ in range(120):  # Wait up to 120 seconds
                    time.sleep(1)
                    session_key = driver.execute_script("""
                        const cookies = document.cookie.split('; ');
                        for (let cookie of cookies) {
                            const [name, value] = cookie.split('=');
                            if (name === 'sessionKey') {
                                return decodeURIComponent(value);
                            }
                        }
                        return null;
                    """)
                    
                    if session_key and session_key.startswith("sk-ant"):
                        driver.quit()
                        return session_key
                
                driver.quit()
                raise click.ClickException("Login timeout - no valid session key found")
                
        except WebDriverException as e:
            if "chromedriver" in str(e).lower():
                raise click.ClickException(
                    "ChromeDriver not found. Please install it:\n"
                    "  Download from: https://chromedriver.chromium.org/\n"
                    "  Or install via package manager:\n"
                    "    - Windows: choco install chromedriver\n"
                    "    - macOS: brew install chromedriver\n"
                    "    - Linux: sudo apt-get install chromium-chromedriver"
                )
            raise click.ClickException(f"Browser automation failed: {str(e)}")
    
    @staticmethod
    def _get_chrome_profile_path() -> str:
        """Get Chrome default profile path."""
        system = platform.system()
        home = os.path.expanduser("~")
        
        if system == "Windows":
            return os.path.join(home, "AppData", "Local", "Google", "Chrome", "User Data")
        elif system == "Darwin":  # macOS
            return os.path.join(home, "Library", "Application Support", "Google", "Chrome")
        else:  # Linux
            return os.path.join(home, ".config", "google-chrome")
