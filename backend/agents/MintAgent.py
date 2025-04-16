# backend/agents/MintAgent.py

import os
import json
import requests # Added
from dotenv import load_dotenv
from agno.agent import Agent
from agno.models.openai import OpenAIChat
from backend.config import NMKR_API_KEY, NMKR_PROJECT_UID # Import from config

# Load environment variables (e.g., NMKR_API_KEY)
# load_dotenv() # REMOVED

# Use NMKR Testnet (Preprod) endpoint
NMKR_API_BASE_URL = "https://studio-api.preprod.nmkr.io/v2"

# TODO: Implement or import a tool for NMKR API minting interaction
# from agno.tools.nmkr import NmkrMintTool # Example

# 🪙 MintAgent: Mints NFTs via NMKR API
mint_agent = Agent(
    name="MintAgent",
    model=OpenAIChat(id="gpt-4o"),
    description="Handles communication with the NMKR API to mint NFTs on Cardano.",
    # tools=[NmkrMintTool()], # Add tool once available
    instructions=[
        # Adjusted instructions based on orchestration flow
        "Receive the specific NMKR NFT UID for the asset to be minted.",
        "Receive the target user's wallet address.",
        "Receive the NMKR Project UID.",
        "Optionally, receive the final CIP-25 metadata (although NMKR might use metadata associated during upload or require an update step prior).",
        "Use the NMKR API endpoint 'MintAndSendSpecific' to mint the NFT identified by the NFT UID to the target wallet.",
        "Assume quantity (count) is 1 unless specified otherwise.",
        "Log any errors during the minting process.",
        "Return the successfully generated minting transaction hash."
    ],
    markdown=True,
    # verbose=True # Optional: for debugging
)

# Updated placeholder function for NMKR minting logic
def mint_nft_with_nmkr(metadata: dict, wallet_address: str, project_uid: str, nft_uid: str) -> str | None:
    """Mints a specific NFT using NMKR MintAndSendSpecific endpoint.
    Returns the transaction hash or None on failure.
    Metadata parameter is currently unused in this implementation, assuming NMKR uses
    metadata associated during UploadNft or requires a separate UpdateMetadata call.
    """
    nmkr_api_key = NMKR_API_KEY
    # project_uid is passed as arg

    if not nmkr_api_key:
        print("Error: NMKR_API_KEY not configured. Cannot mint.")
        return None
    if not project_uid:
        print("Error: NMKR_PROJECT_UID not configured / provided. Cannot mint.")
        return None
    if not nft_uid:
        print("Error: NMKR NFT UID not provided. Cannot mint.")
        return None
    if not wallet_address:
        print("Error: Target wallet address not provided. Cannot mint.")
        return None

    nft_name = metadata.get('name', nft_uid) # Use name from metadata for logging if available
    print(f"Initiating mint for NFT UID: {nft_uid} (Name: '{nft_name}') in Project: {project_uid} to Wallet: {wallet_address}...")

    # Using MintAndSendSpecific endpoint
    mint_endpoint = f"{NMKR_API_BASE_URL}/MintAndSendSpecific/{project_uid}/{nft_uid}/1/{wallet_address}"
    headers = {"Authorization": f"Bearer {nmkr_api_key}"}

    try:
        print(f"Calling NMKR MintAndSendSpecific: GET {mint_endpoint}")
        response = requests.get(mint_endpoint, headers=headers, timeout=60) # GET request as per docs
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        mint_data = response.json()

        # Extract mintAndSendId - txhash is not returned here
        mint_and_send_id = mint_data.get("mintAndSendId") 
        # tx_hash = mint_data.get("txhash") # This key doesn't exist in this response

        if mint_and_send_id:
            print(f"NMKR Mint initiated successfully: MintAndSend ID={mint_and_send_id}")
            # Return the ID or a success indicator. For now, return a placeholder string.
            # A real system would need to track this ID.
            return f"mint_initiated_{mint_and_send_id}"
        else:
            print(f"Error: Could not extract mintAndSendId from NMKR response: {mint_data}")
            return None

    except requests.exceptions.Timeout:
        print(f"Error: Timeout during NMKR MintAndSendSpecific API call for NFT UID {nft_uid}.")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Error calling NMKR MintAndSendSpecific API for NFT UID {nft_uid}: {e}")
        try:
            print(f"Response Status: {e.response.status_code}")
            print(f"Response Body: {e.response.text}")
        except AttributeError:
            print("No response body available.")
        return None
    except Exception as e:
        print(f"An unexpected error occurred during NMKR minting for NFT UID {nft_uid}: {e}")
        return None


# Example usage (for testing within this file)
if __name__ == "__main__":
    # Example data (needs valid config in .env)
    test_metadata = {
        "name": "TestNFT_From_MintAgent",
        "image": "ipfs://QmPlaceholderExample"
    }
    test_wallet = "addr1qxxxx...testwallet...xxxx" # Use a valid Preprod address
    test_project_uid = NMKR_PROJECT_UID # Get from config/env
    test_nft_uid = "YOUR_TEST_NFT_UID_FROM_UPLOAD" # Replace with a UID from a previous test upload

    print("Testing MintAgent (mint_nft_with_nmkr function simulation):")
    print(f" Project UID: {test_project_uid}")
    print(f" NFT UID: {test_nft_uid}")
    print(f" Target Wallet: {test_wallet}")

    if not test_project_uid or test_project_uid == "your_nmkr_project_uid":
         print("\nWarning: NMKR_PROJECT_UID not set or is default in .env")
    elif not test_nft_uid or test_nft_uid == "YOUR_TEST_NFT_UID_FROM_UPLOAD":
        print("\nWarning: test_nft_uid not set. Please run AssetAgent test first and paste a valid UID here.")
    else:
        tx_hash = mint_nft_with_nmkr(test_metadata, test_wallet, test_project_uid, test_nft_uid)

        if tx_hash:
            print("\nMint Simulation Result (Transaction Hash):")
            print(tx_hash)
        else:
            print("\nMint Simulation Failed.")

    # How the agent might actually run:
    # prompt = f"Mint NFT with UID {test_nft_uid} from project {test_project_uid} to wallet {test_wallet}."
    # response = mint_agent.run(prompt)
    # print("\nActual Agent Response (Conceptual):")
    # print(response)
