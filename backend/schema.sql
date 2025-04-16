-- Database Schema for Agno NFT Creator Agent
-- Based on backend_structure_document.mdc

-- Ensure extensions are enabled if needed (e.g., for UUID generation)
-- CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Table for job tracking
CREATE TABLE IF NOT EXISTS jobs (
    id SERIAL PRIMARY KEY,                    -- Unique job identifier
    -- user_id VARCHAR(255) NOT NULL,         -- Link to user (if auth is implemented)
    status VARCHAR(50) NOT NULL DEFAULT 'Pending', -- e.g., Pending, Processing, Success, Failed
    collection_name VARCHAR(255),           -- Name of the NFT collection
    wallet_address VARCHAR(255),             -- User's target wallet address
    creative_prompt TEXT,                    -- Prompt used for generation (if any)
    error_message TEXT,                      -- Store error details if job fails
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Table for storing asset details and IPFS links
CREATE TABLE IF NOT EXISTS assets (
    id SERIAL PRIMARY KEY,
    job_id INTEGER REFERENCES jobs(id) ON DELETE CASCADE,
    original_path_or_url TEXT NOT NULL,      -- The original file path or URL provided/generated
    ipfs_uri VARCHAR(255) NOT NULL UNIQUE,   -- The resulting IPFS URI (e.g., ipfs://...)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Table for metadata storage (CIP-25 compliant JSON)
-- One row per NFT within a job
CREATE TABLE IF NOT EXISTS metadata (
    id SERIAL PRIMARY KEY,
    job_id INTEGER REFERENCES jobs(id) ON DELETE CASCADE,
    asset_id INTEGER REFERENCES assets(id) ON DELETE SET NULL, -- Link to the specific asset
    metadata_json JSONB NOT NULL,            -- The CIP-25 JSON metadata
    nft_name VARCHAR(255),                   -- Extracted NFT name for easier querying
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Table for storing minting transaction details
CREATE TABLE IF NOT EXISTS transactions (
    id SERIAL PRIMARY KEY,
    job_id INTEGER REFERENCES jobs(id) ON DELETE CASCADE,
    metadata_id INTEGER REFERENCES metadata(id) ON DELETE SET NULL, -- Link to the specific NFT metadata
    transaction_hash VARCHAR(255) NOT NULL UNIQUE, -- Cardano transaction hash
    status VARCHAR(50) DEFAULT 'Submitted',   -- e.g., Submitted, Confirmed, Failed
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Table for logging system events and agent steps (optional but helpful)
CREATE TABLE IF NOT EXISTS logs (
    id SERIAL PRIMARY KEY,
    job_id INTEGER REFERENCES jobs(id) ON DELETE CASCADE,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    log_level VARCHAR(50) DEFAULT 'INFO',    -- e.g., INFO, WARNING, ERROR
    agent_name VARCHAR(100),                 -- Which agent generated the log
    message TEXT NOT NULL
);

-- Optional: Function to automatically update 'updated_at' timestamps
CREATE OR REPLACE FUNCTION trigger_set_timestamp()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply the trigger to the jobs table
DROP TRIGGER IF EXISTS set_timestamp ON jobs;
CREATE TRIGGER set_timestamp
BEFORE UPDATE ON jobs
FOR EACH ROW
EXECUTE FUNCTION trigger_set_timestamp();

-- (Add similar triggers for other tables if needed)

-- --- Indexes for performance (Optional but recommended) ---
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_wallet_address ON jobs(wallet_address);
CREATE INDEX IF NOT EXISTS idx_assets_job_id ON assets(job_id);
CREATE INDEX IF NOT EXISTS idx_metadata_job_id ON metadata(job_id);
CREATE INDEX IF NOT EXISTS idx_transactions_job_id ON transactions(job_id);
CREATE INDEX IF NOT EXISTS idx_logs_job_id ON logs(job_id);
CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON logs(timestamp); 