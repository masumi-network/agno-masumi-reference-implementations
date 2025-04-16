# backend/config.py

import os
from dotenv import load_dotenv

# Load .env file from the project root (adjust path if needed)
# Assuming .env is in the parent directory of backend/
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(dotenv_path=dotenv_path)

# Supabase Configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY") # Typically the service_role key for backend operations
SUPABASE_CONNECTION_STRING = os.getenv("SUPABASE_CONNECTION_STRING") # For direct DB connection if needed

# OpenAI Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# NMKR Configuration
NMKR_API_KEY = os.getenv("NMKR_API_KEY")
NMKR_PROJECT_UID = os.getenv("NMKR_PROJECT_UID") # Needs to be set based on your NMKR project

# Masumi Configuration
MASUMI_API_KEY = os.getenv("MASUMI_API_KEY")
MASUMI_PAYMENT_URL = os.getenv("MASUMI_PAYMENT_URL", "https://api.masumi.network")

# Hot Wallet (Optional - for demo)
HOT_WALLET_MNEMONIC = os.getenv("HOT_WALLET_MNEMONIC")

# --- Validation --- (Optional: Add checks to ensure critical variables are set)
def check_env_vars():
    required_vars = {
        # "SUPABASE_URL": SUPABASE_URL,
        # "SUPABASE_KEY": SUPABASE_KEY,
        "OPENAI_API_KEY": OPENAI_API_KEY,
        "NMKR_API_KEY": NMKR_API_KEY,
        "NMKR_PROJECT_UID": NMKR_PROJECT_UID,
        # "MASUMI_API_KEY": MASUMI_API_KEY, # Enable if Masumi is actively used
    }
    missing_vars = [name for name, value in required_vars.items() if not value]
    if missing_vars:
        print(f"Warning: Missing required environment variables: {', '.join(missing_vars)}")
        print("Please ensure they are set in your .env file or environment.")
        return False
    return True

# Run checks when module is imported (optional)
# check_env_vars() 