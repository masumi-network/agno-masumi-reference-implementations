# backend/agents/ContentCreatorAgent.py

import os
# from dotenv import load_dotenv # Keep import if used elsewhere, but remove call # Already removed
from agno.agent import Agent
from agno.models.openai import OpenAIChat
# from agno.tools.openai import DalleTool # REMOVED - Tool does not exist
import openai # Import the openai library directly

# Load environment variables (especially OPENAI_API_KEY)
# load_dotenv() # REMOVED - Should be loaded by app.py now

# --- OpenAI v1.x Client Initialization ---
# We should only initialize the client if the API key exists
client: openai.OpenAI | None = None
openai_api_key = os.getenv("OPENAI_API_KEY")
if openai_api_key:
    client = openai.OpenAI(api_key=openai_api_key)
else:
    print("Warning: OPENAI_API_KEY not found in environment. DALL-E generation will fail.")
# --- End Client Initialization ---

# Define default image generation parameters as per PRD
DEFAULT_IMAGE_SIZE = "1024x1024"
DEFAULT_IMAGE_STYLE = "surreal, ethereal, dreamlike forest"
DEFAULT_IMAGE_COUNT = 1 # How many images to generate per prompt call
DEFAULT_DALLE_MODEL = "dall-e-3" # Or "dall-e-2"

# 🎨 ContentCreatorAgent: Optional content generation based on prompt
# Agent definition remains, but without the DalleTool
content_creator_agent = Agent(
    name="ContentCreatorAgent",
    model=OpenAIChat(id="gpt-4o"), # This agent could still be used for *deciding* to generate, etc.
    description="Generates creative content (e.g. images) based on a user prompt when no files are provided.",
    # tools=[], # No DalleTool
    instructions=[
        f"Based on the user prompt, generate {DEFAULT_IMAGE_COUNT} image(s).",
        f"The desired style is '{DEFAULT_IMAGE_STYLE}'.",
        f"Ensure the image size is {DEFAULT_IMAGE_SIZE}.",
        "Return a list of image URLs."
        # Instructions might need adjustment if the agent isn't directly calling a tool
    ],
    markdown=True,
    # verbose=True # Optional: for debugging tool calls
)

# Function to generate images directly using OpenAI API (v1.x syntax)
def generate_dalle_image(prompt: str, n: int = DEFAULT_IMAGE_COUNT, size: str = DEFAULT_IMAGE_SIZE, style_hint: str = DEFAULT_IMAGE_STYLE) -> list[str]:
    """Generates images using DALL-E via direct OpenAI API call (v1.x) and returns a list of URLs."""
    if not client:
        print("Error: OpenAI client not initialized (API key likely missing). Cannot generate image.")
        return []

    full_prompt = f"{prompt}, style: {style_hint}" # Combine prompt and style hint
    print(f"Generating DALL-E image with prompt: '{full_prompt}', model: {DEFAULT_DALLE_MODEL}, size: {size}, n: {n}")

    try:
        # Using openai v1.x syntax client.images.generate
        response = client.images.generate(
            model=DEFAULT_DALLE_MODEL,
            prompt=full_prompt,
            n=n,
            size=size,
            response_format="url" # Request URLs directly
            # quality="standard" or "hd" # Optional
            # style="vivid" or "natural" # Optional
        )

        image_urls = [img_data.url for img_data in response.data if img_data.url is not None]
        print(f"Generated image URLs: {image_urls}")
        return image_urls
    # Corrected error catching for openai v1.x
    except openai.APIError as e:
        # Handles API errors like rate limits, authentication, etc.
        print(f"OpenAI API error during DALL-E generation: {e}")
        return []
    except Exception as e:
        print(f"An unexpected error occurred during DALL-E generation: {e}")
        return []


# Example usage (for testing within this file)
if __name__ == "__main__":
    if not client:
        print("Error: OPENAI_API_KEY environment variable not set or client failed initialization.")
    else:
        test_prompt = "misty forest with glowing mushrooms"
        print(f"Testing direct DALL-E generation with prompt: '{test_prompt}'")
        urls = generate_dalle_image(test_prompt, n=1) # Generate 1 image for test
        print("\nResponse URLs:")
        print(urls) 