# Agno NFT Creator Agent (MintMind Team Demo)

## Project Overview

This project implements an automated NFT minting solution on the Cardano blockchain (Pre-production Testnet) using the Agno agent framework. The primary goal is to demonstrate a pipeline that takes user input (collection details, creative prompt), optionally generates image assets using OpenAI's DALL-E, uploads assets to IPFS via the NMKR API, generates basic metadata, initiates the minting process via the NMKR API, and logs the results to a Supabase database.

This was developed as a hackathon-style demo, prioritizing the end-to-end workflow over production-level robustness, error handling, and security.

## Current Status (as of completion of initial implementation)

*   **Working End-to-End Pipeline (Demo):** The core workflow from frontend input to mint initiation is functional on the Cardano Preprod testnet.
*   **Frontend:** A basic Streamlit UI (`frontend/app.py`) accepts user input (collection name, prompt, wallet address).
*   **Backend:** A FastAPI application (`backend/app.py`) serves as the backend, orchestrating the workflow.
*   **Agent Structure:** Specialized agent files (`backend/agents/`) exist for different tasks (Content Creation, Asset Upload, Metadata, Minting, Wallet, Payment, Job Orchestration), although the orchestration is currently handled directly within the FastAPI endpoint for simplicity.
*   **DALL-E Integration:** Successfully generates images based on user prompts using direct OpenAI API calls (`backend/agents/ContentCreatorAgent.py`). *(Note: Uses direct calls due to issues with Agno's DalleTool)*.
*   **NMKR Integration:**
    *   Successfully uploads generated assets (or assets from URLs) to IPFS via the NMKR UploadNft API (`backend/agents/AssetAgent.py`).
    *   Successfully initiates the minting process for the uploaded asset via the NMKR MintAndSendSpecific API (`backend/agents/MintAgent.py`).
*   **Metadata Generation:** A placeholder `MetadataAgent` attempts to generate CIP-25 metadata based on inputs. *(Note: Currently simulated via LLM call within the main endpoint)*.
*   **Wallet Validation:** Basic format validation for Cardano addresses (Mainnet `addr1` and Testnet `addr_test1`) is implemented (`backend/agents/WalletAgent.py`).
*   **Database Logging:** Job details, status, asset info (IPFS URI, NMKR UID), and initiated mint IDs are successfully logged to Supabase PostgreSQL tables (`backend/agents/JobAgent.py` & `backend/schema.sql`).
*   **Dependencies & Workarounds:**
    *   Requires `openai==0.28.1` due to compatibility issues between `agno==1.3.1` and `openai>=1.0.0`.
    *   The installed `agno` library required manual patching (`agno/models/openai/responses.py`) to resolve import/type errors related to OpenAI v1.x structures.

## How to Run

### Prerequisites

*   Python 3.10 or higher
*   An NMKR Studio Account ([https://studio.nmkr.io/](https://studio.nmkr.io/)) with a **Preprod Testnet Project** created.
*   A Supabase Account ([https://supabase.com/](https://supabase.com/)) with a project created.
*   An OpenAI API Key ([https://platform.openai.com/](https://platform.openai.com/)).
*   A Cardano Preprod Testnet Wallet (e.g., Eternl, Nami) funded with **tADA** from the faucet ([https://docs.cardano.org/cardano-testnets/tools/faucet](https://docs.cardano.org/cardano-testnets/tools/faucet)).
*   Mint Credits added to your **NMKR Studio Preprod Account** to cover API minting fees.

### Setup Instructions

1.  **Clone the Repository:**
    ```bash
    git clone <your-repo-url>
    cd agno-nft-creator-agent
    ```
2.  **Create Virtual Environment:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```
3.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
    *(Note: This installs specific versions, including `openai==0.28.1`. If you encounter issues, you might need to manually apply the patches to `agno/models/openai/responses.py` as done during development)*
4.  **Configure Environment Variables:**
    *   Copy the example file: `cp .env.example .env`
    *   Edit the `.env` file and fill in your actual values for:
        *   `SUPABASE_URL` (From Supabase project settings > API)
        *   `SUPABASE_KEY` (The `service_role` key from Supabase project settings > API)
        *   `OPENAI_API_KEY`
        *   `NMKR_API_KEY` (The **Preprod Testnet** key from NMKR Studio Account > API Keys)
        *   `NMKR_PROJECT_UID` (The UID of your **Preprod Testnet** project in NMKR Studio)
        *   _(Optional)_ `MASUMI_API_KEY`
        *   _(Optional)_ `HOT_WALLET_MNEMONIC`
5.  **Set up Supabase Database Schema:**
    *   Log in to your Supabase project dashboard.
    *   Navigate to the "SQL Editor".
    *   Click "+ New query".
    *   Copy the entire content of `backend/schema.sql`.
    *   Paste the SQL into the editor and click "Run". Verify it completes successfully.
6.  **Fund NMKR Preprod Account:** Ensure you have added Mint Credits to your NMKR Studio **Preprod** account balance to cover API minting fees.

### Running the Application

1.  **Start Backend Server:**
    *   Open a terminal in the project root (with `venv` activated).
    *   Run: `uvicorn backend.app:app --host 127.0.0.1 --port 8000 --reload`
    *   Watch for successful startup and Supabase client initialization messages.
2.  **Start Frontend Application:**
    *   Open a *second* terminal in the project root (with `venv` activated).
    *   Run: `streamlit run frontend/app.py`
    *   The Streamlit UI should open in your browser.
3.  **Use the App:**
    *   Enter a Collection Name.
    *   Enter a Creative Prompt (e.g., "surreal space landscape").
    *   Enter your **Preprod Testnet** wallet address (starting with `addr_test1...`).
    *   Click "Start NFT Creation Job".
    *   Observe the results in the UI, the backend terminal logs, and your Supabase tables. The NFT should appear in your Preprod wallet after a short delay.

## Project Structure

```
.
├── .env.example        # Example environment variables
├── .gitignore          # Git ignore file
├── backend/            # FastAPI backend code
│   ├── agents/         # Agno agent definitions
│   │   ├── AssetAgent.py
│   │   ├── ContentCreatorAgent.py
│   │   ├── JobAgent.py
│   │   ├── MetadataAgent.py
│   │   ├── MintAgent.py
│   │   ├── PaymentAgent.py
│   │   └── WalletAgent.py
│   ├── app.py          # FastAPI application setup and endpoints
│   ├── config.py       # Loads environment variables
│   └── schema.sql      # SQL schema for Supabase database
├── frontend/           # Streamlit frontend code
│   └── app.py          # Main Streamlit application file
├── requirements.txt    # Python dependencies
└── README.md           # This file
└── venv/               # Python virtual environment (created locally)

```

## Implemented Workflow (Current Demo)

1.  User submits collection name, prompt, and wallet address via Streamlit UI.
2.  Frontend sends a POST request to the backend (`/start_job`).
3.  Backend (`app.py` endpoint) receives the request.
4.  **Wallet Validation:** User's address format (`addr1` or `addr_test1`) is checked (`WalletAgent.py` logic).
5.  **Content Creation:** If prompt provided, DALL-E is called directly via OpenAI API to generate an image URL (`ContentCreatorAgent.py` logic).
6.  **Asset Upload:** The generated image URL is passed to the NMKR UploadNft API, uploading the asset to IPFS and returning an `nftUid` and `ipfsHashMainnft` (`AssetAgent.py` logic).
7.  **Metadata Generation:** The `MetadataAgent` is called (simulated run) with collection details and the IPFS URI to generate CIP-25 JSON. *(Currently parses the direct string output)*.
8.  **Payment Initiation:** Placeholder runs (`PaymentAgent.py` logic).
9.  **NFT Minting:** The NMKR MintAndSendSpecific API is called using the `nftUid` from the upload step and the user's wallet address (`MintAgent.py` logic). It receives a `mintAndSendId` upon successful initiation.
10. **Database Logging:** The job details, generated data (IPFS URI, NMKR UID), metadata (if parsed), mint initiation ID, and final status are logged to the respective tables in Supabase (`JobAgent.py` logic).
11. **Response:** The backend returns a JSON response to the frontend summarizing the outcome.

## Next Steps / Future Work

*   **Refine Metadata Generation:** Replace the simulated `MetadataAgent` call in `app.py` with a proper `agent.run()` call and robust parsing of the `RunResponse` content, ensuring valid CIP-25 JSON is always produced.
*   **Implement Payment Agent:** Replace the placeholder `initiate_masumi_payment` function with actual Masumi API calls if pay-per-mint functionality is desired.
*   **Transaction Hash Retrieval:** Implement logic to retrieve the final Cardano transaction hash after minting (e.g., potentially by polling an NMKR endpoint using the `mintAndSendId`). Store the actual hash in the `transactions` table.
*   **Robust Error Handling:** Improve error handling throughout the pipeline (e.g., handle partial failures, provide clearer user feedback on the frontend).
*   **True Agent Orchestration:** Refactor the orchestration logic from `backend/app.py` into the `JobAgent.py` itself, potentially using Agno's `Team` or more advanced workflow features.
*   **Configuration:** Move hardcoded values (like payment flags, prices) into `backend/config.py` or separate configuration files.
*   **Asynchronous Operations:** Convert long-running tasks (DALL-E generation, uploads, minting) to run asynchronously using FastAPI's `BackgroundTasks` or a task queue (Celery) to prevent blocking the API endpoint.
*   **Security:** Implement proper security measures if moving beyond a demo (authentication, input sanitization, secure key management).
*   **Local File Upload:** Implement handling for actual file uploads from the user via the Streamlit UI and backend.
*   **Agno Compatibility:** Monitor `agno` and `openai` libraries for updates that resolve the compatibility issues, removing the need for manual patches and specific version pinning.
*   **User Interface:** Enhance the Streamlit UI to show job progress more dynamically and display results more elegantly.
*   **Documentation:** Add more detailed code comments and potentially API documentation.

## Known Issues / Limitations (Current Demo)

*   Relies on a specific older version of `openai` (`0.28.1`).
*   Requires manually patched files within the installed `agno` library (`agno/models/openai/responses.py`) due to internal inconsistencies.
*   Metadata generation uses a simulated agent call within the endpoint.
*   Payment step is a placeholder.
*   Relies on the assumption that the order of generated metadata matches the order of uploaded assets for linking (fragile).
*   Entire process runs synchronously within the API request.
*   Minimal security considerations.
*   Doesn't retrieve or store the final blockchain transaction hash for the mint. 