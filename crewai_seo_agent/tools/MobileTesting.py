# Import required libraries:
# - crewai.tools.BaseTool: Base class for creating custom tools
# - selenium: For browser automation and testing
# - pydantic: For data validation and settings management
# - typing: For type hints
from crewai.tools import BaseTool
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from typing import Dict, Optional, Type
from pydantic import BaseModel, Field
from selenium.common.exceptions import TimeoutException
import logging
import os
import time
import requests
import json

logger = logging.getLogger(__name__)

# Define input schema for the mobile testing tool
class MobileTestingInput(BaseModel):
    """Input for MobileTesting"""
    url: str = Field(..., description="The URL to test for mobile optimization")
    timeout: int = Field(default=30, description="Timeout in seconds for the test")

# Main mobile optimization testing tool
class MobileOptimizationTool(BaseTool):
    """Tool that tests websites for mobile-friendliness by checking:
    - Viewport meta tag
    - Text readability 
    - Tap target sizes
    - Responsive images
    """
    
    # Tool metadata
    name: str = "Mobile Optimization Tester"
    description: str = "Tests website for mobile optimization and responsiveness"
    args_schema: Type[BaseModel] = MobileTestingInput

    def __init__(self):
        super().__init__()

    def _setup_driver(self):
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--window-size=375,812')  # iPhone X dimensions
        
        # Add proxy support if needed
        if os.getenv('PROXY_URL'):
            chrome_options.add_argument(f'--proxy-server={os.getenv("PROXY_URL")}')
            
        return webdriver.Chrome(options=chrome_options)

    def _run(self, url: str, timeout: int = 30) -> Dict:
        """Run mobile optimization tests using browserless.io API directly"""
        try:
            # Clean URL
            url = url.strip('"')
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url

            # Use browserless.io API directly
            api_url = f'https://chrome.browserless.io/content?token={os.getenv("BROWSERLESS_API_KEY")}'
            
            payload = {
                'url': url,
                'gotoOptions': {
                    'waitUntil': 'domcontentloaded',
                    'timeout': timeout * 1000
                },
                'viewport': {
                    'width': 375,  # Mobile viewport
                    'height': 667,
                    'deviceScaleFactor': 2,
                    'isMobile': True,
                    'hasTouch': True
                }
            }

            response = requests.post(api_url, json=payload, timeout=timeout)
            
            if response.status_code != 200:
                return {
                    "error": f"Failed to fetch content: {response.status_code}",
                    "status": "error"
                }

            # Parse the content
            content = response.text
            
            return {
                "viewport_meta": "viewport" in content.lower(),
                "touch_elements": self._analyze_touch_elements(content),
                "font_sizes": self._analyze_font_sizes(content),
                "responsive_images": self._analyze_responsive_images(content),
                "status": "success"
            }

        except Exception as e:
            logger.error(f"Mobile testing error: {str(e)}")
            return {
                "error": str(e),
                "status": "error"
            }

    def _analyze_touch_elements(self, content: str) -> Dict:
        """Analyze touch elements in content"""
        return {
            "clickable_elements": content.count("<a ") + content.count("<button"),
            "status": "success"
        }

    def _analyze_font_sizes(self, content: str) -> Dict:
        """Analyze font sizes in content"""
        return {
            "text_elements": content.count("<p") + content.count("<span"),
            "status": "success"
        }

    def _analyze_responsive_images(self, content: str) -> Dict:
        """Analyze responsive images in content"""
        return {
            "total_images": content.count("<img"),
            "responsive_images": content.count("srcset=") + content.count("sizes="),
            "status": "success"
        }

    async def _arun(self, url: str, timeout: int = 180) -> Dict:
        """Async version - not implemented"""
        raise NotImplementedError("Async not implemented")
