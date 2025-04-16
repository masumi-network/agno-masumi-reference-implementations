# backend/agents/WalletAgent.py

import os
import re # For basic regex validation
from dotenv import load_dotenv
from agno.agent import Agent
from agno.models.openai import OpenAIChat

# Load environment variables (e.g., HOT_WALLET_MNEMONIC - if needed later)
# load_dotenv()

# 💼 WalletAgent: Manages internal wallet + user routing
wallet_agent = Agent(
    name="WalletAgent",
    model=OpenAIChat(id="gpt-4o"),
    description="Validates user Cardano wallet addresses and handles aspects of transaction signing.",
    # No specific tools needed for basic validation, relies on instructions/logic
    instructions=[
        "Receive a Cardano wallet address provided by the user.",
        "Perform a basic validation check on the address format.",
        "The address should typically start with 'addr1'.",
        # "Ensure it meets basic length and character set requirements for Cardano addresses.", # Model can infer this
        "If the address format is invalid, return an error message.",
        "If the address format is valid, confirm its validity.",
        "Prepare the internal hot wallet environment for transaction signing (this is a simplified step for the demo).",
        "Return a status indicating whether the address is valid and the hot wallet is ready (simulated)."
    ],
    markdown=True,
    # verbose=True # Optional: for debugging
)

# Placeholder function for basic Cardano address validation
def validate_cardano_address(address: str) -> bool:
    """Performs a very basic format check for a Cardano address (Mainnet or Testnet)."""
    if not address:
        return False
    # Basic check: starts with addr1 or addr_test1 and has a reasonable length
    # This is NOT a cryptographic validation, just a format sanity check.
    # Allows both mainnet (addr1) and testnet (addr_test1) prefixes
    pattern = r"^(addr1|addr_test1)[a-z0-9]{90,}$"
    # Cardano addresses have variable length, typically > 95-105 chars.
    # A more robust check might involve bech32 decoding or a dedicated library.
    if re.match(pattern, address):
        # Add more checks if needed (e.g., length range)
        return True
    print(f"Address '{address}' failed regex pattern match.") # Added log for failure
    return False

# Placeholder for hot wallet preparation
def prepare_hot_wallet() -> bool:
    """Simulates preparing the hot wallet."""
    # In a real scenario, this would involve loading keys, checking balances etc.
    # hot_wallet_mnemonic = os.getenv("HOT_WALLET_MNEMONIC")
    # if not hot_wallet_mnemonic:
    #     print("Error: HOT_WALLET_MNEMONIC not set.")
    #     return False
    print("[Placeholder] Hot wallet prepared for signing.")
    return True

# Example usage (for testing within this file)
if __name__ == "__main__":
    test_addresses = [
        "addr1qyphrwr7g60sgcygt0cfqrnplp0gvz8r3fqe4mctp4n9z7k6dwyqe35w9rkxqclv3qx3w9g3rzyda3z6e9qrj6z2k0fsrd7j4y", # Valid format example
        "addr1invalidaddress",
        "stake1uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx", # Stake address (invalid for payment)
        ""
    ]

    print("Testing WalletAgent (validation simulation):")
    for addr in test_addresses:
        is_valid = validate_cardano_address(addr)
        hot_wallet_ready = prepare_hot_wallet() if is_valid else False
        print(f"Address: '{addr}'")
        print(f"  Is Valid Format: {is_valid}")
        print(f"  Hot Wallet Ready: {hot_wallet_ready}")
        print("---")

    # How the agent might actually run:
    # valid_addr = test_addresses[0]
    # response = wallet_agent.run(f"Validate this Cardano address and prepare for signing: {valid_addr}")
    # print("\nActual Agent Response (Conceptual):")
    # print(response) 