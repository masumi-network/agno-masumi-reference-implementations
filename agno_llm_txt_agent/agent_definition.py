from textwrap import dedent
from typing import Dict, Any, Iterator, Optional
import os
import json
import time
import requests
import boto3
from logging_config import get_logger
from agno.agent import Agent, RunResponse
from agno.models.openai import OpenAIChat
from agno.workflow import Workflow
from agno.utils.log import logger
from dotenv import load_dotenv
import logging
from urllib.parse import urlparse, quote
import re


# Load environment variables and configure logging
load_dotenv()
logger = get_logger(__name__)
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

class LLMsTxtGeneratorWorkflow(Workflow):
    """Workflow for generating LLMs.txt files from websites and providing download links"""
    
    description: str = (
        "Generate LLMs.txt files from websites using Firecrawl API and upload to Digital Ocean for download"
    )
    
    def __init__(self, debug_mode: bool = False, **kwargs):
        super().__init__(debug_mode=debug_mode)
        # Support either a single URL string or a list of URLs
        urls = kwargs.get("urls", kwargs.get("url", ""))
        self.urls = [urls] if isinstance(urls, str) and urls else urls if isinstance(urls, list) else []
        self.max_urls = kwargs.get("max_urls", 15)
        self.show_full_text = kwargs.get("show_full_text", True)
        self.api_key = os.environ.get("FIRECRAWL_API_KEY", "")
        
        # Digital Ocean Spaces credentials
        self.do_key = os.environ.get("DO_SPACES_KEY", "")
        self.do_secret = os.environ.get("DO_SPACES_SECRET", "")
        self.do_region = os.environ.get("DO_SPACES_REGION", "nyc3")
        self.do_bucket = os.environ.get("DO_SPACES_BUCKET", "")
    
    def _generate_file_name(self, urls: list) -> str:
        """Generate a clean file name based on the website URLs"""
        if not urls:
            return "llm-combined.txt"
        
        if len(urls) == 1:
            # Single URL case
            parsed_url = urlparse(urls[0])
            domain = parsed_url.netloc
            
            # Remove www. prefix if present
            if domain.startswith('www.'):
                domain = domain[4:]
            
            # Replace dots and other non-alphanumeric characters with hyphens
            clean_domain = re.sub(r'[^a-zA-Z0-9]', '-', domain)
            file_name = f"llm-{clean_domain}.txt"
        else:
            # Multiple URLs case - use first domain plus count
            parsed_url = urlparse(urls[0])
            main_domain = parsed_url.netloc
            if main_domain.startswith('www.'):
                main_domain = main_domain[4:]
            
            clean_domain = re.sub(r'[^a-zA-Z0-9]', '-', main_domain)
            file_name = f"llm-{clean_domain}-plus-{len(urls)-1}.txt"
        
        return file_name

    def run(self) -> Iterator[RunResponse]:
        """
        Execute the LLMs.txt generation and upload workflow, returning Markdown output.
        
        Returns:
            Iterator of RunResponse objects with results of each step in Markdown format.
        """
        # Validate input data - Return Markdown errors
        if not self.urls:
            error_md = "# LLMs.txt Generation Failed\n\n**Error:** At least one website URL is required."
            yield RunResponse(run_id=self.run_id, content=error_md)
            return
        
        if not self.api_key:
            error_md = "# LLMs.txt Generation Failed\n\n**Error:** Firecrawl API key is not configured."
            yield RunResponse(run_id=self.run_id, content=error_md)
            return
            
        if not self.do_key or not self.do_secret or not self.do_bucket:
            error_md = "# LLMs.txt Generation Failed\n\n**Error:** Digital Ocean Spaces credentials are not configured."
            yield RunResponse(run_id=self.run_id, content=error_md)
            return
            
        # Process each URL and combine the results
        combined_content = []
        processed_urls = []
        failed_urls = []
        
        for url in self.urls:
            try:
                # Generate LLMs.txt file
                logger.info(f"Generating LLMs.txt for URL: {url}")
                llms_txt_response = self._generate_llms_txt(url)
                
                if not llms_txt_response or not isinstance(llms_txt_response, dict) or not llms_txt_response.get("success"):
                    logger.error(f"Failed to start LLMs.txt generation for {url}: {llms_txt_response}")
                    failed_urls.append(url)
                    continue
                
                generation_id = llms_txt_response.get("id")
                logger.info(f"LLMs.txt generation started with ID: {generation_id}")
                
                llms_txt_content = self._check_generation_status(generation_id)
                
                if not llms_txt_content:
                    logger.error(f"Failed to retrieve generated LLMs.txt content for {url}")
                    failed_urls.append(url)
                    continue
                
                combined_content.append(f"\n\n{'='*50}\n# URL: {url}\n{'='*50}\n\n{llms_txt_content}")
                processed_urls.append(url)
                
            except Exception as e:
                logger.error(f"Error processing URL {url}: {str(e)}")
                failed_urls.append(url)
        
        # --- Format Output as Markdown ---
        
        if not processed_urls:
            failed_urls_md = "\n".join([f"- {url}" for url in failed_urls])
            error_md = f"# LLMs.txt Generation Failed\n\n**Error:** Failed to process any URLs.\n\n**Failed URLs:**\n{failed_urls_md}"
            yield RunResponse(run_id=self.run_id, content=error_md)
            return
        
        # Combine all content
        combined_text = "# Combined LLMs.txt\n" + "\n".join(combined_content)
        
        # Upload to Digital Ocean Spaces
        logger.info("Uploading combined LLMs.txt to Digital Ocean Spaces...")
        file_name = self._generate_file_name(processed_urls)
        # Ensure filename is URL-safe for the download link
        safe_file_name = quote(file_name) 
        download_url = self._upload_to_do_spaces(combined_text, file_name) # Use original filename for upload
        
        if not download_url:
            error_md = "# LLMs.txt Generation Failed\n\n**Error:** Failed to upload combined LLMs.txt to Digital Ocean Spaces."
            yield RunResponse(run_id=self.run_id, content=error_md)
            return

        # Construct the success Markdown output
        markdown_output = ["# LLMs.txt Generation Report", ""] 
        markdown_output.append("**Status:** Success")
        markdown_output.append("")
        
        markdown_output.append("**Processed URLs:**")
        for url in processed_urls:
            markdown_output.append(f"- {url}")
        markdown_output.append("")

        if failed_urls:
            markdown_output.append("**Failed URLs:**")
            for url in failed_urls:
                markdown_output.append(f"- {url}")
            markdown_output.append("")
            
        # Use the original filename for display, safe filename for the URL itself
        markdown_output.append(f"**Download Link:** [{file_name}]({download_url.replace(file_name, safe_file_name)})") 
        
        final_markdown = "\n".join(markdown_output)
        
        yield RunResponse(run_id=self.run_id, content=final_markdown)
    
    def _generate_llms_txt(self, url: str) -> Dict[str, Any]:
        """Call Firecrawl API to start LLMs.txt generation"""
        api_url = "https://api.firecrawl.dev/v1/llmstxt"
        
        payload = {
            "url": url,
            "maxUrls": self.max_urls,
            "showFullText": self.show_full_text
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.post(api_url, json=payload, headers=headers)
            return response.json()
        except Exception as e:
            logger.error(f"Error calling Firecrawl API: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def _check_generation_status(self, generation_id: str, max_attempts: int = 30) -> Optional[str]:
        """Check LLMs.txt generation status until complete"""
        api_url = f"https://api.firecrawl.dev/v1/llmstxt/{generation_id}"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # Poll for status with exponential backoff
        attempts = 0
        while attempts < max_attempts:
            try:
                response = requests.get(api_url, headers=headers)
                data = response.json()
                
                if data.get("status") == "completed":
                    # Extract content from the correct nested location
                    # Use llmsfulltxt instead of llmstxt when available
                    if self.show_full_text and data.get("data", {}).get("llmsfulltxt"):
                        return data.get("data", {}).get("llmsfulltxt")
                    return data.get("data", {}).get("llmstxt")
                elif data.get("status") == "failed":
                    logger.error(f"LLMs.txt generation failed: {data.get('error')}")
                    return None
                
                # Wait with exponential backoff (starting at 2 seconds)
                wait_time = min(2 * (2 ** attempts), 60)  # Cap at 60 seconds
                logger.info(f"Generation in progress, waiting {wait_time} seconds...")
                time.sleep(wait_time)
                attempts += 1
                
            except Exception as e:
                logger.error(f"Error checking generation status: {str(e)}")
                time.sleep(5)
                attempts += 1
        
        logger.error("Max attempts reached while waiting for LLMs.txt generation")
        return None
    
    def _upload_to_do_spaces(self, content: str, file_name: str) -> Optional[str]:
        """Upload content to Digital Ocean Spaces and return download URL"""
        try:
            # Create S3 client
            s3_client = boto3.client(
                's3',
                region_name=self.do_region,
                endpoint_url=f'https://{self.do_region}.digitaloceanspaces.com',
                aws_access_key_id=self.do_key,
                aws_secret_access_key=self.do_secret
            )
            
            # Upload file
            s3_client.put_object(
                Bucket=self.do_bucket,
                Key=file_name,
                Body=content.encode('utf-8'),
                ACL='public-read',
                ContentType='text/plain'
            )
            
            # Generate download URL
            download_url = f'https://{self.do_bucket}.{self.do_region}.digitaloceanspaces.com/{file_name}'
            return download_url
            
        except Exception as e:
            logger.error(f"Error uploading to Digital Ocean Spaces: {str(e)}")
            return None


# Function to run the workflow with specified parameters
def run_workflow(urls, max_urls: int = 15, show_full_text: bool = True) -> Iterator[RunResponse]:
    """
    Run the LLMsTxtGeneratorWorkflow with the given parameters.
    
    Args:
        urls: Website URL or list of URLs to generate LLMs.txt from
        max_urls: Maximum number of URLs to analyze per site (default: 15)
        show_full_text: Whether to include full text content (default: True)
        
    Returns:
        Iterator of RunResponse objects
    """
    workflow = LLMsTxtGeneratorWorkflow(
        debug_mode=True,
        urls=urls,
        max_urls=max_urls,
        show_full_text=show_full_text
    )
    return workflow.run()


# Execute the LLMs.txt generation workflow with the provided input data
async def execute_agno_task(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """Execute the LLMs.txt generation workflow with the provided input data"""
    logger.info(f"Starting LLMs.txt generation workflow with input: {input_data}")
    
    # Extract parameters from input data - support both 'url' and 'urls'
    urls = input_data.get("urls", input_data.get("url", ""))
    max_urls = input_data.get("max_urls", 15)
    show_full_text = input_data.get("show_full_text", True)
    
    # Run the workflow with the parameters
    responses = list(run_workflow(
        urls=urls,
        max_urls=max_urls,
        show_full_text=show_full_text
    ))
    
    # Get the final response
    final_response = responses[-1] if responses else None
    
    if final_response and final_response.content:
        try:
            # Try to parse the content as JSON
            result = json.loads(final_response.content)
            return result
        except json.JSONDecodeError:
            # If not JSON, return as plain text
            return {"result": final_response.content}
    else:
        return {"error": "No response from workflow"}


if __name__ == "__main__":
    # Test data
    test_data = {
        "urls": ["https://masumi.network", "https://docs.masumi.network"],
        "max_urls": 15,
        "show_full_text": True
    }
    
    # Run the workflow directly (synchronous)
    print("Starting workflow test...")
    responses = run_workflow(
        urls=test_data["urls"],
        max_urls=test_data["max_urls"],
        show_full_text=test_data["show_full_text"]
    )
    
    for response in responses:
        print(f"Response: {response.content}")
    
    print("Workflow test completed.")