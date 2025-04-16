import os
import json
from dotenv import load_dotenv

# --- Load Environment Variables First --- 
# Assuming .env is in the parent directory (project root)
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(dotenv_path=dotenv_path)
print(f"Attempted to load .env file from: {dotenv_path}")
# Check if a key is loaded (optional debug)
# print(f"OPENAI_API_KEY loaded: {bool(os.getenv('OPENAI_API_KEY'))}") 
# --- End Load Env Vars ---

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Import agent functions/simulation logic (adjust path if needed)
from backend.agents.JobAgent import (
    validate_cardano_address, prepare_hot_wallet,
    upload_to_nmkr_ipfs,
    metadata_agent, # Need agent instance for actual run
    initiate_masumi_payment,
    mint_nft_with_nmkr,
    log_job_to_supabase
)
# Import the direct generation function instead of the agent instance
from backend.agents.ContentCreatorAgent import generate_dalle_image
from backend.config import NMKR_PROJECT_UID # Get NMKR Project UID from config

app = FastAPI(title="Agno NFT Creator Agent Backend")

# Pydantic model for the request body of /start_job
class StartJobRequest(BaseModel):
    collection_name: str
    creative_prompt: str | None = None
    wallet_address: str
    # uploaded_files: list | None = None # Placeholder for file uploads

@app.get("/")
def read_root():
    return {"message": "Welcome to the Agno NFT Creator Agent Backend"}

@app.post("/start_job")
async def start_job(request: StartJobRequest):
    print(f"Received job request: {request.dict()}")
    
    job_request = request.dict()
    nmkr_project_uid = NMKR_PROJECT_UID
    pay_per_mint_enabled = True # TODO: Make configurable
    price_per_nft = 3.0 # TODO: Make configurable (e.g., load from pricing.json)

    final_results = {
        "status": "Processing",
        "job_id": None, # Will be set after logging
        "initial_request": job_request,
        "steps": {}
    }

    # --- Run Orchestration Steps (using imported functions/agents) ---
    try:
        # --- Step 1: Wallet Validation ---
        print("Step 1: Validating Wallet...")
        # Use actual wallet_agent run or the placeholder function
        # is_valid_wallet = wallet_agent.run(f"Validate: {job_request['wallet_address']}") # Example agent call
        is_valid_wallet = validate_cardano_address(job_request["wallet_address"])
        is_hot_wallet_ready = prepare_hot_wallet() if is_valid_wallet else False
        final_results["steps"]["wallet_validation"] = {"is_valid": is_valid_wallet, "hot_wallet_ready": is_hot_wallet_ready}
        if not is_valid_wallet:
            final_results["status"] = "Failed - Invalid Wallet"
            log_job_to_supabase(final_results) # Log failure
            raise HTTPException(status_code=400, detail=f"Invalid Cardano wallet address format: {job_request['wallet_address']}")
        print("Wallet Validated.")

        # --- Step 2: Content Creation (Conditional) ---
        image_urls = []
        if not job_request.get("uploaded_files") and job_request.get("creative_prompt"):
            print("Step 2: Generating Content...")
            # Actual agent call needed here -> Now using direct function call
            try:
                # Ensure OPENAI_API_KEY is available (handled in ContentCreatorAgent module)
                # generated_content = content_creator_agent.run(job_request["creative_prompt"])
                image_urls = generate_dalle_image(job_request["creative_prompt"])
                # Basic parsing attempt - adjust based on actual DalleTool output format
                # The direct function already returns a list of URLs
                if not isinstance(image_urls, list):
                     print(f"Warning: generate_dalle_image did not return a list: {image_urls}")
                     image_urls = [] # Reset if format is wrong

                print(f"Generated content URLs: {image_urls}")
                final_results["steps"]["content_creation"] = {"urls": image_urls}
            except Exception as e:
                print(f"Error during content creation: {e}")
                final_results["status"] = "Failed - Content Creation Error"
                final_results["steps"]["content_creation"] = {"error": str(e)}
                log_job_to_supabase(final_results) # Log failure
                raise HTTPException(status_code=500, detail=f"Content creation failed: {e}")
        else:
            print("Step 2: Skipping Content Generation.")

        # --- Step 3: Asset Upload ---
        # This map will store {original_asset: {"ipfs_uri": ..., "nft_uid": ...}}
        asset_details_map = {}
        assets_to_upload = job_request.get("uploaded_files") or image_urls
        if assets_to_upload:
            print("Step 3: Uploading Assets...")
            upload_success_count = 0
            # Pass collection_name and index to the upload function
            for idx, asset in enumerate(assets_to_upload):
                ipfs_uri, nft_uid = upload_to_nmkr_ipfs(asset, job_request['collection_name'], idx)
                if ipfs_uri and nft_uid:
                    asset_details_map[asset] = {"ipfs_uri": ipfs_uri, "nft_uid": nft_uid}
                    upload_success_count += 1
                else:
                    # Handle upload failure for specific asset
                    print(f"Warning: Failed to upload asset {asset}")
            print(f"IPFS/UID Mapping: {asset_details_map}")
            final_results["steps"]["asset_upload"] = {"uploaded_map": asset_details_map}
            if upload_success_count != len(assets_to_upload): # Check if some uploads failed
                 print("Warning: Some assets failed to upload.")
                 # Optional: Decide if partial failure is job failure
                 # if upload_success_count == 0:
                 #     final_results["status"] = "Failed - All Asset Uploads Failed"
                 #     log_job_to_supabase(final_results)
                 #     raise HTTPException(status_code=500, detail="Failed to upload any assets.")
        else:
            print("Step 3: Skipping Asset Upload (No assets).")

        # --- Step 4: Metadata Generation ---
        metadata_list = []
        if asset_details_map: # Proceed if we have successfully uploaded assets
            print("Step 4: Generating Metadata...")
            try:
                # Construct proper input for MetadataAgent
                ipfs_uri_map_for_meta = {orig: details["ipfs_uri"] for orig, details in asset_details_map.items()}
                meta_prompt = f"""
                Collection Name: {job_request['collection_name']}
                Assets with IPFS URIs: {json.dumps(ipfs_uri_map_for_meta)}
                Generate a list of CIP-25 JSON metadata objects, one for each asset listed.
                Use the original asset key (e.g., '{list(ipfs_uri_map_for_meta.keys())[0]}') to infer the base name for each NFT if needed.
                Ensure each metadata object includes at least 'name', 'image' (the IPFS URI), and 'mediaType'.
                Return only the raw list of JSON objects.
                """
                # Run the agent and get the RunResponse object
                agent_run_result = metadata_agent.run(meta_prompt)
                # Extract the actual string response (try .content attribute)
                metadata_json_string = None
                if hasattr(agent_run_result, 'content'):
                     metadata_json_string = agent_run_result.content 
                elif hasattr(agent_run_result, 'response'): # Fallback to .response if needed
                     metadata_json_string = agent_run_result.response

                # Attempt to parse the extracted string response
                if metadata_json_string and isinstance(metadata_json_string, str):
                    try:
                        # Clean potential markdown code fences if the LLM added them
                        if metadata_json_string.strip().startswith("```json"): 
                             metadata_json_string = metadata_json_string.strip()[7:-3].strip()
                        elif metadata_json_string.strip().startswith("```"):
                            metadata_json_string = metadata_json_string.strip()[3:-3].strip()
                        
                        parsed_metadata = json.loads(metadata_json_string)
                        if isinstance(parsed_metadata, list):
                            metadata_list = parsed_metadata
                            # TODO: Associate metadata back to nft_uid more reliably
                        else:
                            print(f"Warning: MetadataAgent did not return a JSON list. Output: {metadata_json_string}")
                            metadata_list = []
                    except json.JSONDecodeError as json_error:
                        print(f"Error: Could not parse MetadataAgent JSON string response: {json_error}")
                        # Use triple quotes for multi-line f-string
                        print(f"""--- Agent Response Start ---
{metadata_json_string}
--- Agent Response End ---""")
                        metadata_list = [] # Set to empty on parse failure
                else:
                     print(f"Error: MetadataAgent did not return a valid string response. Got type: {type(metadata_json_string)}")
                     metadata_list = [] # Set to empty if not string

                print(f"Generated Metadata Count: {len(metadata_list)}")
                # Add NFT UIDs to the results for this step if possible (assuming order matches)
                step_4_results = {
                    "metadata_count": len(metadata_list),
                    "metadata_preview": metadata_list[:2], # Store preview
                    "associated_nft_uids": [details.get("nft_uid") for details in asset_details_map.values()]
                 }
                final_results["steps"]["metadata_generation"] = step_4_results
            except Exception as e:
                print(f"Error during metadata generation: {e}")
                final_results["status"] = "Failed - Metadata Generation Error"
                final_results["steps"]["metadata_generation"] = {"error": str(e)}
                log_job_to_supabase(final_results) # Log failure
                raise HTTPException(status_code=500, detail=f"Metadata generation failed: {e}")
        else:
            print("Step 4: Skipping Metadata Generation.")

        # --- Step 5: Payment Initiation ---
        payment_info = None
        if pay_per_mint_enabled and metadata_list:
            print("Step 5: Initiating Payment...")
            payment_info = initiate_masumi_payment(len(metadata_list), price_per_nft) # Using placeholder
            print(f"Payment Info: {payment_info}")
            final_results["steps"]["payment_initiation"] = payment_info
            if not payment_info: # Handle payment initiation failure
                 print("Error: Payment initiation failed.")
                 final_results["status"] = "Failed - Payment Initiation Error"
                 log_job_to_supabase(final_results)
                 raise HTTPException(status_code=500, detail="Payment initiation failed.")
            # TODO: Add logic to wait/check payment status if needed
        else:
            print("Step 5: Skipping Payment Initiation.")

        # --- Step 6: NFT Minting ---
        tx_hashes = [] 
        # We need metadata AND corresponding NFT UIDs for minting
        # Assuming metadata_list and asset_details_map values are in corresponding order
        items_to_mint = []
        if metadata_list and len(metadata_list) == len(asset_details_map):
            asset_details_values = list(asset_details_map.values())
            for i, meta in enumerate(metadata_list):
                nft_uid = asset_details_values[i].get("nft_uid")
                if nft_uid:
                    items_to_mint.append({"metadata": meta, "nft_uid": nft_uid})
                else:
                    print(f"Warning: Missing NFT UID for metadata index {i}, cannot mint this item.")
        
        can_mint = bool(items_to_mint) # TODO: Add payment status check if needed
        if can_mint:
            print(f"Step 6: Minting {len(items_to_mint)} NFTs...")
            if not nmkr_project_uid:
                 final_results["status"] = "Failed - NMKR Project UID not configured"
                 log_job_to_supabase(final_results)
                 raise HTTPException(status_code=500, detail="NMKR_PROJECT_UID is not set in environment.")

            # TODO: Replace with actual MintAgent call or loop with placeholder
            for item in items_to_mint:
                # Pass metadata AND the specific nft_uid to the minting function
                tx_hash = mint_nft_with_nmkr(item["metadata"], job_request["wallet_address"], nmkr_project_uid, item["nft_uid"]) # Pass nft_uid
                if tx_hash:
                    tx_hashes.append(tx_hash)
                else:
                    print(f"Warning: Failed to mint NFT with UID: {item['nft_uid']}")
            
            print(f"Transaction Hashes: {tx_hashes}")
            final_results["steps"]["nft_minting"] = {"tx_hashes": tx_hashes}
            if len(tx_hashes) == len(items_to_mint):
                final_results["status"] = "Success"
            elif len(tx_hashes) > 0:
                final_results["status"] = "Partial Success - Some Minting Errors"
            else:
                final_results["status"] = "Failed - All Minting Errors"
        else:
             print("Step 6: Skipping NFT Minting (Prerequisites not met or no items prepared).)")
             if final_results["status"] == "Processing": # Only update if not already failed
                 final_results["status"] = "Completed - Nothing to Mint"

    except HTTPException as http_exc: # Catch handled exceptions
        print(f"HTTP Exception caught: {http_exc.detail}")
        # Status already set and logged in the raising step
        raise http_exc # Re-raise to return proper HTTP response
    except Exception as e:
        print(f"An unexpected error occurred during orchestration: {e}")
        final_results["status"] = "Failed - Unexpected Error"
        final_results["steps"]["orchestration_error"] = str(e)
        # Attempt to log the error before raising HTTP exception
        log_job_to_supabase(final_results)
        raise HTTPException(status_code=500, detail=f"Job failed due to an unexpected error: {e}")
    finally:
        # --- Step 7: Database Logging (Final Update) ---
        print("Step 7: Logging Final Job Status to Database...")
        # log_job_to_supabase might log intermediate steps, 
        # this call ensures the final status is logged or updated.
        # If job_id exists, we should UPDATE instead of INSERT. 
        # Simplified: we just call log again, which inserts a new record in this impl.
        # TODO: Implement UPDATE logic if job_id was previously obtained.
        job_id = log_job_to_supabase(final_results)
        if job_id:
            final_results["job_id"] = job_id # Add job_id to the response
        final_results["steps"]["database_log"] = {"status": "Logged (Final)"}

    # --- Step 8: Final Response --- 
    print("Step 8: Returning Final Response.")
    return final_results

# Configuration for running the app with uvicorn directly
if __name__ == "__main__":
    import uvicorn
    # It's recommended to run via the command line: 
    # uvicorn backend.app:app --host 0.0.0.0 --port 8000 --reload
    # But this allows running `python backend/app.py` for simple testing
    print("Starting Uvicorn server...")
    uvicorn.run("backend.app:app", host="127.0.0.1", port=8000, reload=True) 