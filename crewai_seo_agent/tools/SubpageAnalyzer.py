from crewai.tools import BaseTool
from typing import Type, Optional, Dict, List
from pydantic import BaseModel, Field
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import logging
import time
import os

logger = logging.getLogger(__name__)

class SubpageAnalyzerInput(BaseModel):
    """Input parameters for subpage analysis"""
    website_url: str = Field(..., description="The URL of the website to analyze")
    max_pages: int = Field(default=10, description="Maximum number of subpages to analyze")
    min_content_length: int = Field(default=100, description="Minimum content length to consider")

class SubpageAnalyzer(BaseTool):
    name: str = "Subpage Analyzer"
    description: str = """
    Analyzes website subpages by:
    - Finding all accessible pages
    - Analyzing content quality
    - Measuring user engagement signals
    - Ranking pages by importance
    """
    args_schema: Type[BaseModel] = SubpageAnalyzerInput

    def _run(self, website_url: str, max_pages: int = 10, min_content_length: int = 100) -> str:
        try:
            # Use browserless.io for initial page fetch
            api_url = f'https://chrome.browserless.io/content?token={os.getenv("BROWSERLESS_API_KEY")}'
            
            payload = {
                'url': website_url,
                'gotoOptions': {
                    'waitUntil': 'domcontentloaded',
                    'timeout': 30000
                }
            }

            response = requests.post(api_url, json=payload, timeout=30)
            
            if response.status_code != 200:
                return "No subpages found or analysis failed"

            # Parse content and find links
            soup = BeautifulSoup(response.text, 'html.parser')
            links = self._extract_links(soup, website_url)
            
            # Analyze found pages
            analyzed_pages = []
            for link in links[:max_pages]:
                page_data = self._analyze_page(link)
                if page_data and page_data.get('content_length', 0) >= min_content_length:
                    analyzed_pages.append(page_data)

            return self._format_results(analyzed_pages)

        except Exception as e:
            logger.error(f"Subpage analysis error: {str(e)}")
            return "Analysis failed: " + str(e)

    def _extract_links(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """Extract valid internal links from page"""
        base_domain = urlparse(base_url).netloc
        links = set()
        
        for a in soup.find_all('a', href=True):
            href = a['href']
            full_url = urljoin(base_url, href)
            
            if urlparse(full_url).netloc == base_domain:
                links.add(full_url)
                
        return list(links)

    def _analyze_page(self, url: str) -> Optional[Dict]:
        """Analyze a single page"""
        try:
            # Use browserless.io for consistent page fetching
            api_url = f'https://chrome.browserless.io/content?token={os.getenv("BROWSERLESS_API_KEY")}'
            
            payload = {
                'url': url,
                'gotoOptions': {
                    'waitUntil': 'domcontentloaded',
                    'timeout': 20000
                }
            }

            response = requests.post(api_url, json=payload, timeout=20)
            
            if response.status_code != 200:
                return None

            soup = BeautifulSoup(response.text, 'html.parser')
            
            return {
                'url': url,
                'title': soup.title.string if soup.title else url,
                'content_length': len(soup.get_text()),
                'headings': len(soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])),
                'images': len(soup.find_all('img')),
                'internal_links': len([a for a in soup.find_all('a', href=True) 
                                    if not a['href'].startswith(('http', 'https'))]),
                'external_links': len([a for a in soup.find_all('a', href=True) 
                                    if a['href'].startswith(('http', 'https'))]),
                'importance_score': self._calculate_importance(soup)
            }
        except Exception as e:
            logger.error(f"Page analysis error for {url}: {str(e)}")
            return None

    def _calculate_importance(self, soup: BeautifulSoup) -> float:
        """Calculate page importance score"""
        score = 0
        score += len(soup.find_all(['h1', 'h2', 'h3'])) * 2
        score += len(soup.find_all('a', href=True))
        score += len(soup.find_all('img')) * 0.5
        score += len(soup.get_text()) * 0.01
        return score

    def _format_results(self, analyzed_pages: List[Dict]) -> str:
        """Formats analysis results into a readable report"""
        if not analyzed_pages:
            return "No subpages found or analysis failed"
            
        # Sort pages by importance score
        sorted_pages = sorted(analyzed_pages, key=lambda x: x['importance_score'], reverse=True)
        
        report = ["=== Top Subpages Analysis ===\n"]
        
        if sorted_pages[0]['url'] in ['No subpages found', 'Analysis failed']:
            report.append("No accessible subpages found or analysis failed")
            return "\n".join(report)
        
        for i, page in enumerate(sorted_pages[:10], 1):
            report.append(f"{i}. {page['title']}")
            report.append(f"   URL: {page['url']}")
            report.append(f"   Metrics:")
            report.append(f"   - Content Length: {page['content_length']} characters")
            report.append(f"   - Headings: {page['headings']}")
            report.append(f"   - Images: {page['images']}")
            report.append(f"   - Internal Links: {page['internal_links']}")
            report.append(f"   - External Links: {page['external_links']}")
            report.append(f"   - Importance Score: {page['importance_score']:.2f}\n")
        
        # Add summary statistics
        if len(analyzed_pages) > 0:
            avg_score = sum(p['importance_score'] for p in analyzed_pages) / len(analyzed_pages)
            report.append(f"\nAnalysis Summary:")
            report.append(f"- Total Pages Analyzed: {len(analyzed_pages)}")
            report.append(f"- Average Importance Score: {avg_score:.2f}")
        
        return "\n".join(report) 