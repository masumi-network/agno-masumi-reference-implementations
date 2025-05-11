# src/crew.py
from crewai import Agent, Crew, Process, Task, LLM
from crewai.project import CrewBase, agent, crew, task
from dotenv import load_dotenv
import openai
import os
from tools.LoadingTimeTracker import LoadingTimeTracker
from tools.MobileTesting import MobileOptimizationTool
from tools.SubpageAnalyzer import SubpageAnalyzer
from tools.BrowserlessScraper import BrowserlessScraper
import asyncio
from typing import Dict, Any, List
import logging
from logging_config import get_logger

logger = logging.getLogger(__name__)

load_dotenv()

class AgentConfig:
    """Configuration for all agents used in the SEO analysis"""
    
    SCRAPER_AGENT = {
        'role': 'Web Scraping Specialist',
        'goal': 'Efficiently collect and organize website data for SEO analysis',
        'backstory': '''You are an expert web scraper with years of experience in data collection 
        and website analysis. Your specialty is gathering comprehensive data while respecting 
        website policies and performance constraints.'''
    }
    
    ANALYSE_AGENT = {
        'role': 'SEO Data Analyst',
        'goal': 'Analyze collected website data to identify SEO strengths and weaknesses',
        'backstory': '''You are a seasoned SEO analyst with a strong background in data 
        interpretation and pattern recognition. You excel at turning raw website data into 
        actionable insights.'''
    }
    
    OPTIMIZATION_AGENT = {
        'role': 'SEO Optimization Specialist',
        'goal': 'Develop actionable recommendations for SEO improvement',
        'backstory': '''You are a strategic SEO consultant with extensive experience in 
        website optimization. You specialize in creating practical, high-impact recommendations 
        that deliver measurable results.'''
    }

class TaskConfig:
    """Configuration for all tasks in the SEO analysis process"""
    
    @staticmethod
    def get_data_collection_task(website_url: str) -> Dict[str, str]:
        return {
            'description': f'''Collect comprehensive data from {website_url} including:
            1. Page load times
            2. Mobile responsiveness metrics
            3. Content structure
            4. Meta information
            5. Internal linking patterns
            Please use the provided tools to gather this information efficiently.''',
            
            'expected_output': f'''A detailed report containing:
            1. Technical metrics for {website_url}
            2. Content inventory
            3. Meta tag analysis
            4. Site structure overview
            5. Performance metrics'''
        }
    
    @staticmethod
    def get_analysis_task(website_url: str) -> Dict[str, str]:
        return {
            'description': f'''Analyze the collected data for {website_url} to identify:
            1. SEO strengths
            2. Areas for improvement
            3. Technical issues
            4. Content gaps
            5. Competitive positioning''',
            
            'expected_output': '''A comprehensive analysis including:
            1. Key findings
            2. Priority issues
            3. Opportunity areas
            4. Risk factors
            5. Comparative analysis'''
        }
    
    OPTIMIZATION_TASK = {
        'description': '''Based on the analysis, create an actionable optimization plan:
        1. Prioritized recommendations
        2. Implementation steps
        3. Expected impact
        4. Resource requirements
        5. Timeline estimates''',
        
        'expected_output': '''A structured optimization plan including:
        1. Priority Fixes
        2. Impact Forecast
        3. Key Statistics
        4. Page-Specific Optimizations
        5. Implementation Timeline'''
    }

@CrewBase
class SEOAnalysisCrew():
    """
    Main class that orchestrates the SEO analysis process using multiple AI agents.
    It handles data collection, analysis, and optimization recommendations.
    """
    
    def __init__(self, website_url: str, verbose=True, logger=None):
        self.website_url = website_url
        self.verbose = verbose
        self.logger = logger or get_logger(__name__)
        
        # Initialize tools
        self.tools = [
            BrowserlessScraper(),
            LoadingTimeTracker(),
            MobileOptimizationTool(),
            SubpageAnalyzer()
        ]
        
        self.crew = self.create_crew()
        self.logger.info(f"SEOAnalysisCrew initialized for {website_url}")

    openai_llm = LLM(
        model='gpt-4o',
        api_key=os.getenv('OPENAI_API_KEY'),
        max_retries=3,
        temperature=0.5
    )

    def create_crew(self):
        self.logger.info("Creating SEO analysis crew with agents")
        
        scraper_agent = Agent(
            role="SEO Technical Auditor and Data Collector",
            goal="Efficiently collect and analyze website data for comprehensive SEO audits, including technical elements, content metrics, and competitor analysis",
            backstory="""You're an expert in technical SEO auditing and web scraping, specializing in gathering
            comprehensive website data. Your strength lies in identifying and extracting key SEO metrics
            like meta tags, site structure, page speed, mobile optimization, and content quality signals.""",
            tools=self.tools,
            verbose=self.verbose
        )

        analyse_agent = Agent(
            role="SEO Analytics and Insights Specialist",
            goal="Perform in-depth analysis of SEO data to uncover ranking opportunities and optimization insights",
            backstory="""You're a skilled SEO analyst with extensive experience in processing and interpreting website
            performance data. Your expertise lies in analyzing keyword rankings, search trends, technical SEO
            metrics, and competitor data to identify strategic opportunities for improvement.""",
            verbose=self.verbose
        )

        optimization_agent = Agent(
            role="SEO Strategy and Implementation Expert",
            goal="Develop and prioritize actionable SEO optimization strategies based on technical and competitive analysis",
            backstory="""You're a seasoned SEO optimization specialist who excels at creating comprehensive improvement
            plans. Your focus is on developing actionable strategies for technical SEO, content optimization,
            link building, and mobile optimization to improve search rankings and organic traffic.""",
            verbose=self.verbose
        )

        self.logger.info("Created all SEO analysis agents")

        # Define tasks with full configuration from tasks.yaml
        data_collection_task = Task(
            description=f"""
            WEBSITE BEING ANALYZED: {self.website_url}

            Analyze and collect SPECIFIC metrics using the tools:
            1. Using BrowserlessScraper, collect and analyze:
               - Meta tags and SEO elements
               - Content structure (headings h1-h6)
               - Keyword frequency and density analysis
               - Internal and external link mapping
               - Images and media inventory
               - Complete URL directory
               - Meta descriptions extraction

            2. Using SubpageAnalyzer, analyze:
               - Page crawl and indexing status
               - Content quality assessment
               - User engagement metrics
               - Internal linking patterns
               - Page authority scoring
               - JavaScript-rendered content

            3. Using LoadingTimeTracker:
               - Page load timing analysis
               - Resource loading sequences
               - Performance bottlenecks
               - Network request patterns
               - Page size measurements
               - Performance ratings

            4. Using MobileTesting:
               - Viewport configuration
               - Mobile responsiveness
               - Touch element spacing
               - Font size accessibility
               - Content scaling
               - Mobile-friendly images
               - Media query implementation
               - Mobile performance metrics
               - User experience factors

            IMPORTANT: Provide NUMERICAL data wherever possible. Do not make assumptions.
            """,
            expected_output=f"""
            ANALYSIS REPORT FOR: {self.website_url}

            1. Meta Tags Analysis:
               - Total number of meta tags: [X]
               - Most used meta tags:
                 * [tag_type]: [count] occurrences
            
            2. Content Analysis:
               - Most frequent words and density percentages
            
            3. Content Structure:
               - H1-H6 tag counts
               - Total word count
            
            4. Link Analysis:
               - Internal/External link counts
               - Unique domains linked
               - Broken links found
            
            5. Complete Media Inventory
            
            6. Performance Metrics:
               - Load time statistics
               - Mobile optimization scores
            
            7. Top Subpages Analysis
            """,
            agent=scraper_agent
        )

        analysis_task = Task(
            description=f"""
            ANALYZING WEBSITE: {self.website_url}

            Based on the collected numerical data, analyze:
            1. Technical Performance
            2. Content Quality
            3. Link Profile
            4. Page Importance
            """,
            expected_output="""
            Comprehensive analysis including:
            1. Performance Scores
            2. Content Metrics
            3. Link Analysis
            4. Page Authority Analysis
            """,
            agent=analyse_agent
        )

        optimization_task = Task(
            description="""
            Based on the analysis, create an actionable optimization plan with:
            1. Priority Issues (List top 5 with metrics)
            2. Expected Impact (Percentage improvements)
            3. Implementation Timeline (With specific milestones)
            4. Page-Specific Recommendations
            """,
            expected_output="""
            Detailed optimization plan including:
            1. Priority Fixes
            2. Impact Forecast
            3. Key Statistics
            4. Page-Specific Optimizations
            5. Implementation Timeline
            """,
            agent=optimization_agent
        )

        crew = Crew(
            agents=[scraper_agent, analyse_agent, optimization_agent],
            tasks=[data_collection_task, analysis_task, optimization_task]
        )
        
        self.logger.info("Crew setup completed")
        return crew

    def run(self) -> str:
        """Run the SEO analysis crew and return raw results"""
        try:
            self.logger.info("Starting SEO analysis")
            result = self.crew.kickoff()
            self.logger.info("SEO analysis completed successfully")
            return result
        except Exception as e:
            self.logger.error(f"Error during SEO analysis: {str(e)}")
            return str(e)

if __name__ == "__main__":
    # Test the SEO Analysis Crew with masumi.network
    test_url = "https://www.masumi.network/"
    print(f"Testing SEO Analysis Crew with {test_url}")
    
    try:
        # Check for required environment variables
        if not os.getenv('OPENAI_API_KEY'):
            raise ValueError("OPENAI_API_KEY environment variable is not set")
        if not os.getenv('BROWSERLESS_API_KEY'):
            raise ValueError("BROWSERLESS_API_KEY environment variable is not set")
            
        # Initialize the crew
        seo_crew = SEOAnalysisCrew(website_url=test_url, verbose=True)
        
        # Run the analysis
        print("Starting SEO analysis...")
        result = seo_crew.run()
        
        # Print the results
        print("\n=== SEO ANALYSIS RESULTS ===\n")
        print(result)
        print("\n=== ANALYSIS COMPLETE ===")
        
    except Exception as e:
        print(f"\nError: {str(e)}")
        print("\nPlease make sure you have:")
        print("1. Set up your .env file with required API keys")
        print("2. Installed all required dependencies")
        print("3. Have a working internet connection")