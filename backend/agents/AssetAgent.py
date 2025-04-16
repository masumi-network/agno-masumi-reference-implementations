# backend/agents/AssetAgent.py

import os
import json
import requests
import tempfile
import mimetypes
import re
import base64 # Added for Base64 encoding
import time # Added for timestamp
from dotenv import load_dotenv
from agno.agent import Agent
from agno.models.openai import OpenAIChat
from backend.config import NMKR_API_KEY, NMKR_PROJECT_UID # Import from config

# Load environment variables (e.g., NMKR_API_KEY)
# load_dotenv() # REMOVED - Should be loaded by app.py now

# TODO: Implement or import a tool for NMKR API interaction (specifically for uploads)
# from agno.tools.nmkr import NmkrUploadTool # Example - This tool doesn't exist yet

# Use NMKR Testnet (Preprod) endpoint
NMKR_API_BASE_URL = "https://studio-api.preprod.nmkr.io/v2"

# 🧱 AssetAgent: Uploads assets to IPFS
asset_agent = Agent(
    name="AssetAgent",
    model=OpenAIChat(id="gpt-4o"),
    description="Handles uploading user assets (local files or URLs) to IPFS via NMKR.",
    # tools=[NmkrUploadTool()], # Add tool once available
    instructions=[
        "Receive a list of asset file paths or image URLs.",
        "For each asset, prepare a JSON payload and call the NMKR API UploadNft endpoint.",
        "If the asset is a URL, use the 'fileFromsUrl' field in the JSON.",
        "If the asset is a local file, read it, Base64 encode it, and use the 'fileFromBase64' field.",
        "If an upload fails, log the error and attempt to continue with other assets.",
        "Return a dictionary mapping the original filename or URL to a tuple containing its (IPFS URI, NMKR NFT UID).",
        "Ensure the mapping only includes successful uploads."
    ],
    markdown=True,
    # verbose=True # Optional: for debugging
)

# Updated function for NMKR upload logic based on Documentation
def upload_to_nmkr_ipfs(asset_path_or_url: str, collection_name: str, index: int) -> tuple[str | None, str | None]:
    """Uploads an asset (URL or local path) via NMKR UploadNft endpoint using JSON body.
    Generates tokenname based on collection_name and index.
    Returns a tuple (ipfs_uri, nft_uid) or (None, None) on failure.
    Reference: https://docs.nmkr.io/nmkr-studio-api/api-examples/project/upload-file-and-metadata
    """
    nmkr_api_key = NMKR_API_KEY
    project_uid = NMKR_PROJECT_UID

    if not nmkr_api_key:
        print("Error: NMKR_API_KEY not configured. Cannot upload.")
        return None, None
    if not project_uid:
        print("Error: NMKR_PROJECT_UID not configured. Cannot upload.")
        return None, None

    # Generate a unique token name using timestamp
    sanitized_collection_name = re.sub(r'[^a-zA-Z0-9_-]', '_', collection_name)
    sanitized_collection_name = sanitized_collection_name[:25] # Keep collection name part shorter
    timestamp_short = str(int(time.time()))[-6:] # Use last 6 digits of timestamp
    # Create token name like CollectionName_001_123456
    token_name = f"{sanitized_collection_name}_{index + 1:03d}_{timestamp_short}"
    token_name = token_name[:64] # Ensure max length
    display_name = token_name # Use the same for display name for simplicity
    
    print(f"Processing asset for NMKR JSON upload: {asset_path_or_url}")
    print(f" Generated Token Name: {token_name}") # Log generated name

    payload_preview_image = {}
    mimetype = 'application/octet-stream' # Default

    # Handle URL
    if asset_path_or_url.startswith('http://') or asset_path_or_url.startswith('https://'):
        print(f"Asset is URL. Using fileFromsUrl.")
        # Attempt to guess mimetype from URL extension, default otherwise
        guessed_type, _ = mimetypes.guess_type(asset_path_or_url)
        mimetype = guessed_type if guessed_type else 'image/png' # Default to image/png for URLs
        payload_preview_image["mimetype"] = mimetype
        payload_preview_image["fileFromsUrl"] = asset_path_or_url

    # Handle Local File Path
    else:
        print(f"Asset is local path. Reading and Base64 encoding.")
        try:
            if not os.path.exists(asset_path_or_url):
                 print(f"Error: Local file not found: {asset_path_or_url}")
                 return None, None
            
            guessed_type, _ = mimetypes.guess_type(asset_path_or_url)
            mimetype = guessed_type if guessed_type else 'application/octet-stream'
            
            with open(asset_path_or_url, 'rb') as f:
                file_content = f.read()
            
            base64_encoded_content = base64.b64encode(file_content).decode('utf-8')
            payload_preview_image["mimetype"] = mimetype
            payload_preview_image["fileFromBase64"] = base64_encoded_content
            print(f"Read and encoded local file ({len(file_content)} bytes).")

        except Exception as e:
            print(f"Error processing local file {asset_path_or_url}: {e}")
            return None, None

    # Construct the final JSON payload
    # Using minimal fields based on documentation example structure
    payload = {
      "tokenname": token_name,       # Use generated name
      "displayname": display_name,   # Use generated name
      "description": f"Asset for {display_name} uploaded via Agno Agent", # Basic description
      "previewImageNft": payload_preview_image
      # Not including: subfiles, metadataPlaceholder, metadataOverride for simplicity
    }

    upload_endpoint = f"{NMKR_API_BASE_URL}/UploadNft/{project_uid}"
    headers = {
        "Authorization": f"Bearer {nmkr_api_key}",
        "Content-Type": "application/json",
        "accept": "text/plain" # As seen in docs curl example header
        }

    try:
        print(f"Calling NMKR UploadNft (JSON): POST {upload_endpoint} for {token_name}")
        # print(f"Payload preview: {json.dumps(payload)[:200]}...") # Optional: Debug payload
        response = requests.post(upload_endpoint, headers=headers, json=payload, timeout=60)
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        upload_data = response.json()

        # Extract required data using keys from documentation response example
        ipfs_hash = upload_data.get("ipfsHashMainnft")
        nft_uid = upload_data.get("nftUid")

        if not ipfs_hash or not nft_uid:
            print(f"Error: Could not extract ipfsHashMainnft or nftUid from NMKR response: {upload_data}")
            return None, None

        # Construct full IPFS URI
        ipfs_uri = f"ipfs://{ipfs_hash}"

        print(f"NMKR Upload successful: NFT UID={nft_uid}, IPFS URI={ipfs_uri}")
        return ipfs_uri, nft_uid

    except requests.exceptions.Timeout:
        print(f"Error: Timeout during NMKR UploadNft API call for {token_name}.")
        return None, None
    except requests.exceptions.RequestException as e:
        print(f"Error calling NMKR UploadNft API: {e}")
        try:
            print(f"Response Status: {e.response.status_code}")
            print(f"Response Body: {e.response.text}")
        except AttributeError:
            print("No response body available.")
        return None, None
    except Exception as e:
        print(f"An unexpected error occurred during NMKR upload: {e}")
        return None, None

# Example usage (for testing within this file)
if __name__ == "__main__":
    # Create a dummy file for local testing
    dummy_file_path = "dummy_asset.png" # Use .png extension
    try:
        # Create a minimal valid PNG file (1x1 pixel transparent)
        png_sig = b'\x89PNG\r\n\x1a\n'
        ihdr_chunk = b'\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89'
        idat_chunk = b'\x00\x00\x00\nIDATx\x9cc\xfc\xff?\x03\x00\x01\xfae\xbd\xfa' # Minimal IDAT
        iend_chunk = b'\x00\x00\x00\x00IEND\xaeB`\x82'
        with open(dummy_file_path, "wb") as f:
             f.write(png_sig + ihdr_chunk + idat_chunk + iend_chunk)
        print(f"Created dummy PNG file: {dummy_file_path}")
    except Exception as e:
        print(f"Could not create dummy PNG file: {e}")
        dummy_file_path = None # Prevent test from running if file creation failed

    test_assets = [
        "https://via.placeholder.com/150.png", # Example URL (use .png)
    ]
    if dummy_file_path and os.path.exists(dummy_file_path):
         test_assets.append(dummy_file_path)

    print(f"Testing AssetAgent with assets: {test_assets}")

    # Simulate the agent run process
    results = {}
    if NMKR_PROJECT_UID and NMKR_PROJECT_UID != "your_nmkr_project_uid":
        for asset in test_assets:
            ipfs_uri, nft_uid = upload_to_nmkr_ipfs(asset, "TestCollection", 0)
            if ipfs_uri and nft_uid:
                results[asset] = {"ipfs_uri": ipfs_uri, "nft_uid": nft_uid}
            else:
                 print(f"Failed to process asset: {asset}")
    else:
        print("Skipping NMKR upload test - NMKR_PROJECT_UID not set.")

    print("\nAgent Run Simulation Result (Asset to IPFS/UID mapping):")
    print(json.dumps(results, indent=2))

    # Clean up dummy file
    if dummy_file_path and os.path.exists(dummy_file_path):
        try:
             os.remove(dummy_file_path)
             print(f"Removed dummy file: {dummy_file_path}")
        except Exception as e:
            print(f"Could not remove dummy file: {e}")

    # How the agent might actually use the function/tool:
    # response = asset_agent.run(f"Upload these assets: {test_assets}")
    # print("\nActual Agent Response (Conceptual):")
    # print(response) 