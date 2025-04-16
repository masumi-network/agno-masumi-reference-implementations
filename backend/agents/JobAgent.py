# backend/agents/JobAgent.py

import os
import json
from dotenv import load_dotenv
from agno.agent import Agent
from agno.models.openai import OpenAIChat

# Import other agents (adjust paths if necessary)
from .ContentCreatorAgent import content_creator_agent # Assuming agents are in the same directory
from .AssetAgent import asset_agent, upload_to_nmkr_ipfs # Import placeholder function for now
from .MetadataAgent import metadata_agent
from .MintAgent import mint_agent, mint_nft_with_nmkr # Import placeholder function
from .WalletAgent import wallet_agent, validate_cardano_address, prepare_hot_wallet # Import placeholders
from .PaymentAgent import payment_agent, initiate_masumi_payment # Import placeholder

# Import Supabase client
from supabase import create_client, Client

# Import config variables
from backend.config import SUPABASE_URL, SUPABASE_KEY

# Initialize Supabase client (only if credentials exist)
supabase: Client | None = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("Supabase client initialized successfully.")
    except Exception as e:
        print(f"Error initializing Supabase client: {e}")
else:
    print("Warning: Supabase URL or Key not set. Database logging will be skipped.")

# 🧠 JobAgent: Orchestrator agent
job_agent = Agent(
    name="JobAgent",
    model=OpenAIChat(id="gpt-4o"),
    description="Orchestrates the full NFT drop pipeline from input to final minting and reporting.",
    # This agent might not need external tools directly, but orchestrates agents that do.
    instructions=[
        "Receive the initial job request including collection name, prompt (optional), wallet address, and potentially uploaded assets.",
        "**Step 1: Wallet Validation:** Call WalletAgent to validate the provided wallet address.",
        "   - If invalid, stop the job and report the error.",
        "**Step 2: Content Creation (Conditional):** If no assets are provided AND a creative prompt exists, call ContentCreatorAgent.",
        "   - Store the generated image URLs/paths.",
        "**Step 3: Asset Upload:** Collate provided assets and/or generated content URLs. Call AssetAgent to upload them to IPFS.",
        "   - Store the mapping of original assets to IPFS URIs.",
        "**Step 4: Metadata Generation:** Call MetadataAgent with collection details and the IPFS URI mapping.",
        "   - Store the generated list of CIP-25 metadata JSON.",
        "**Step 5: Payment Initiation (Conditional):** If using pay-per-mint, call PaymentAgent to get payment details.",
        "   - Store payment UID and address. The workflow might pause here until payment is confirmed (out of scope for basic demo).",
        "**Step 6: NFT Minting:** Call MintAgent with the metadata list, user wallet address, and NMKR project UID.",
        "   - Store the list of transaction hashes.",
        "**Step 7: Database Logging:** Record the entire job details, status, IPFS URIs, metadata, and transaction hashes in the Supabase database.", # Requires Supabase setup
        "**Step 8: Final Response:** Compile a final structured response including status, links (if applicable), metadata summary, and transaction hashes."
    ],
    markdown=True,
    # verbose=True # Optional: for debugging
)

# Updated function for Supabase logging
def log_job_to_supabase(job_data: dict):
    if not supabase:
        print("Warning: Supabase client not initialized. Skipping database logging.")
        return None # Indicate failure or skip

    print(f"Logging job details to Supabase...")

    # --- Prepare data for insertion --- 
    # 1. Insert into 'jobs' table
    job_status = job_data.get("status", "Unknown")
    error_msg = None
    if "Failed" in job_status:
        # Try to extract a more specific error if available
        if job_status == "Failed - Invalid Wallet":
            error_msg = "Invalid wallet address provided."
        # Add other specific error message extractions if needed
        else:
             error_msg = job_status # Store the general failure status
    
    job_payload = {
        "status": job_status,
        "collection_name": job_data.get("initial_request", {}).get("collection_name"),
        "wallet_address": job_data.get("initial_request", {}).get("wallet_address"),
        "creative_prompt": job_data.get("initial_request", {}).get("creative_prompt"),
        "error_message": error_msg
    }
    try:
        job_insert_response = supabase.table('jobs').insert(job_payload).execute()
        if job_insert_response.data:
            job_id = job_insert_response.data[0]['id']
            print(f"Successfully logged job entry with ID: {job_id}")
            
            # --- Log related data using the job_id ---
            # 2. Log assets
            asset_step_data = job_data.get("steps", {}).get("asset_upload", {})
            if asset_step_data and 'ipfs_map' in asset_step_data:
                assets_to_log = [
                    {"job_id": job_id, "original_path_or_url": orig, "ipfs_uri": ipfs}
                    for orig, ipfs in asset_step_data['ipfs_map'].items()
                ]
                if assets_to_log:
                    asset_insert_response = supabase.table('assets').insert(assets_to_log).execute()
                    if asset_insert_response.data:
                        print(f"Logged {len(asset_insert_response.data)} asset(s).")
                        # Store asset IDs if needed for metadata linking (requires returning IDs)
                    else:
                         print(f"Warning/Error logging assets: {asset_insert_response.error}")

            # 3. Log metadata (linking might require asset IDs - simplified for now)
            metadata_step_data = job_data.get("steps", {}).get("metadata_generation", {})
            if metadata_step_data and 'metadata' in metadata_step_data:
                 metadata_to_log = [
                     {"job_id": job_id, "metadata_json": meta, "nft_name": meta.get('name')}
                     for meta in metadata_step_data['metadata']
                 ]
                 if metadata_to_log:
                     metadata_insert_response = supabase.table('metadata').insert(metadata_to_log).execute()
                     if metadata_insert_response.data:
                         print(f"Logged {len(metadata_insert_response.data)} metadata record(s).")
                     else:
                         print(f"Warning/Error logging metadata: {metadata_insert_response.error}")
            
            # 4. Log transactions (linking might require metadata IDs - simplified for now)
            tx_step_data = job_data.get("steps", {}).get("nft_minting", {})
            if tx_step_data and 'tx_hashes' in tx_step_data:
                 transactions_to_log = [
                     {"job_id": job_id, "transaction_hash": tx_hash, "status": "Submitted"}
                     for tx_hash in tx_step_data['tx_hashes']
                 ]
                 if transactions_to_log:
                     tx_insert_response = supabase.table('transactions').insert(transactions_to_log).execute()
                     if tx_insert_response.data:
                         print(f"Logged {len(tx_insert_response.data)} transaction(s).")
                     else:
                         print(f"Warning/Error logging transactions: {tx_insert_response.error}")
            
            # 5. Log general completion message (optional)
            log_payload = {
                "job_id": job_id,
                "log_level": "INFO" if job_status == "Success" else "ERROR",
                "agent_name": "JobAgent",
                "message": f"Job completed with status: {job_status}"
            }
            supabase.table('logs').insert(log_payload).execute() 

            return job_id # Return the ID of the created job record
        else:
            print(f"Error inserting job into Supabase: {job_insert_response.error}")
            return None
    except Exception as e:
        # Ensure the actual exception is printed
        import traceback
        print(f"An unexpected error occurred during Supabase logging: {e}")
        print(f"Job Data causing error: {job_data}") # Print data that failed
        traceback.print_exc() # Print full traceback
        return None


# Example Orchestration Logic (Simplified Simulation within __main__)
if __name__ == "__main__":
    # --- Initial Job Request Data ---
    job_request = {
        "collection_name": "Simulated Otherworlds",
        "creative_prompt": "misty forest with glowing mushrooms", # Simulate needing content generation
        "wallet_address": "addr1qyphrwr7g60sgcygt0cfqrnplp0gvz8r3fqe4mctp4n9z7k6dwyqe35w9rkxqclv3qx3w9g3rzyda3z6e9qrj6z2k0fsrd7j4y",
        "uploaded_files": None # Simulate no files uploaded
    }
    nmkr_project_uid = os.getenv("NMKR_PROJECT_UID", "your_nmkr_project_uid") # Get from env or hardcode for test
    pay_per_mint_enabled = True # Simulate payment enabled
    price_per_nft = 3.0 # Simulate price

    print("--- Starting Job Orchestration Simulation ---")
    print(f"Initial Request: {job_request}")

    final_results = {
        "status": "Failed",
        "initial_request": job_request,
        "steps": {}
    }

    # --- Step 1: Wallet Validation ---
    print("\nStep 1: Validating Wallet...")
    is_valid_wallet = validate_cardano_address(job_request["wallet_address"])
    is_hot_wallet_ready = prepare_hot_wallet() if is_valid_wallet else False
    final_results["steps"]["wallet_validation"] = {"is_valid": is_valid_wallet, "hot_wallet_ready": is_hot_wallet_ready}
    if not is_valid_wallet:
        print("Error: Invalid wallet address. Stopping job.")
        final_results["status"] = "Failed - Invalid Wallet"
        # Log the failure before exiting the simulation
        print("\nStep 7: Logging Job Failure to Database...")
        log_job_to_supabase(final_results)
    else:
        print("Wallet Validated.")
        image_urls = []
        # --- Step 2: Content Creation (Conditional) ---
        if not job_request.get("uploaded_files") and job_request.get("creative_prompt"):
            print("\nStep 2: Generating Content...")
            # Simulate call to ContentCreatorAgent
            # response = content_creator_agent.run(job_request["creative_prompt"])
            # For simulation, assume it returns URLs
            image_urls = [
                "https://simulated_url/image1.png",
                "https://simulated_url/image2.png"
            ]
            print(f"Generated content URLs: {image_urls}")
            final_results["steps"]["content_creation"] = {"urls": image_urls}
        else:
            print("\nStep 2: Skipping Content Generation (Assets provided or no prompt).")

        # --- Step 3: Asset Upload ---
        assets_to_upload = job_request.get("uploaded_files") or image_urls
        if assets_to_upload:
            print("\nStep 3: Uploading Assets...")
            ipfs_map = {}
            for asset in assets_to_upload:
                # Simulate call to AssetAgent/upload function
                uri = upload_to_nmkr_ipfs(asset)
                if uri:
                    ipfs_map[asset] = uri
            print(f"IPFS Mapping: {ipfs_map}")
            final_results["steps"]["asset_upload"] = {"ipfs_map": ipfs_map}
        else:
             print("\nStep 3: Skipping Asset Upload (No assets).")
             ipfs_map = {}

        # --- Step 4: Metadata Generation ---
        if ipfs_map:
            print("\nStep 4: Generating Metadata...")
            # Simulate call to MetadataAgent
            # prompt = f"Details: {job_request['collection_name']}, URIs: {ipfs_map}"
            # response = metadata_agent.run(prompt)
            # Simulate response
            metadata_list = [
                {"name": f"{job_request['collection_name']}_1", "image": ipfs_map.get(list(ipfs_map.keys())[0]), "mediaType": "image/png"},
                {"name": f"{job_request['collection_name']}_2", "image": ipfs_map.get(list(ipfs_map.keys())[1]), "mediaType": "image/png"},
            ]
            print(f"Generated Metadata: {json.dumps(metadata_list, indent=2)}")
            final_results["steps"]["metadata_generation"] = {"metadata": metadata_list}
        else:
            print("\nStep 4: Skipping Metadata Generation (No assets uploaded).")
            metadata_list = []

        # --- Step 5: Payment Initiation ---
        payment_info = None
        if pay_per_mint_enabled and metadata_list:
            print("\nStep 5: Initiating Payment...")
            # Simulate call to PaymentAgent
            payment_info = initiate_masumi_payment(len(metadata_list), price_per_nft)
            print(f"Payment Info: {payment_info}")
            final_results["steps"]["payment_initiation"] = payment_info
            # In real flow, might wait here for payment confirmation
        else:
            print("\nStep 5: Skipping Payment Initiation.")

        # --- Step 6: NFT Minting ---
        tx_hashes = []
        # Proceed only if metadata exists (and optionally, payment is confirmed/not needed)
        can_mint = bool(metadata_list) # Add payment status check if needed
        if can_mint:
            print("\nStep 6: Minting NFTs...")
            for meta in metadata_list:
                # Simulate call to MintAgent
                tx_hash = mint_nft_with_nmkr(meta, job_request["wallet_address"], nmkr_project_uid)
                if tx_hash:
                    tx_hashes.append(tx_hash)
            print(f"Transaction Hashes: {tx_hashes}")
            final_results["steps"]["nft_minting"] = {"tx_hashes": tx_hashes}
            final_results["status"] = "Success" if tx_hashes else "Failed - Minting Errors"
        else:
             print("\nStep 6: Skipping NFT Minting (Prerequisites not met).")
             if final_results["status"] == "Failed": # Keep failure status if already set
                 pass
             else:
                 final_results["status"] = "Completed - Nothing to Mint"


        # --- Step 7: Database Logging ---
        print("\nStep 7: Logging Job to Database...")
        log_job_to_supabase(final_results) # Pass the collected results
        final_results["steps"]["database_log"] = {"status": "Logged (Simulated)"}

    # --- Step 8: Final Response ---
    print("\n--- Job Orchestration Simulation Complete ---")
    print("Final Results:")
    print(json.dumps(final_results, indent=2)) 