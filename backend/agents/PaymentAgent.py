# backend/agents/PaymentAgent.py

import os
import json
import requests
from dotenv import load_dotenv
from agno.agent import Agent
from agno.models.openai import OpenAIChat

# Load environment variables (MASUMI_API_KEY, MASUMI_PAYMENT_URL)
# load_dotenv()

# TODO: Implement or import a tool for Masumi Payment API interaction
# from agno.tools.masumi import MasumiPaymentTool # Example

# 💳 PaymentAgent: Integrates Masumi Payments
payment_agent = Agent(
    name="PaymentAgent",
    model=OpenAIChat(id="gpt-4o"),
    description="Integrates with Masumi Payments for handling pay-per-mint transactions.",
    # tools=[MasumiPaymentTool()], # Add tool once available
    instructions=[
        "Receive job details, including the number of NFTs to be minted and potentially pricing information.",
        "Determine the total cost based on the pay-per-mint model (e.g., using pricing.json or passed parameters).",
        "Initiate a payment request using the Masumi Payment API (/purchase/).",
        "Return the payment transaction UID and payment address to the orchestrator (JobAgent).",
        "Optionally, handle polling for payment status (/proceedpaymenttransaction/{uid}/gettransactionstate) if required by the workflow.",
        "Handle potential errors during the payment initiation process."
    ],
    markdown=True,
    # verbose=True # Optional: for debugging
)

# Placeholder function for initiating Masumi payment
def initiate_masumi_payment(item_count: int, price_per_item_ada: float) -> dict | None:
    masumi_api_key = os.getenv("MASUMI_API_KEY")
    masumi_payment_url = os.getenv("MASUMI_PAYMENT_URL", "https://api.masumi.network") # Default URL from docs
    if not masumi_api_key:
        print("Error: MASUMI_API_KEY not set. Cannot initiate payment.")
        return None

    total_cost = item_count * price_per_item_ada
    print(f"[Placeholder] Initiating Masumi payment for {item_count} items at {price_per_item_ada} ADA each (Total: {total_cost} ADA)...")

    purchase_endpoint = f"{masumi_payment_url}/purchase/"
    headers = {
        "Authorization": f"Bearer {masumi_api_key}",
        "Content-Type": "application/json"
    }
    # Payload structure needs to be confirmed from Masumi docs/examples
    payload = {
        "amount_ada": total_cost, # Example field
        "item_description": f"{item_count} NFT Mint Job", # Example field
        # Add other required fields based on Masumi API spec
    }

    try:
        print(f"[Placeholder] Calling POST {purchase_endpoint}")
        # response = requests.post(purchase_endpoint, headers=headers, json=payload)
        # response.raise_for_status() # Raise exception for bad status codes
        # payment_data = response.json()

        # Simulate success for now
        simulated_response = {
            "paymentTransactionUid": f"simulated_uid_{item_count}_{total_cost}",
            "paymentAddress": "addr1qxsimulatedpaymentaddress...",
            "status": "pending"
        }
        print(f"[Placeholder] Masumi response: {simulated_response}")
        return simulated_response

    except requests.exceptions.RequestException as e:
        print(f"Error calling Masumi API: {e}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred during payment initiation: {e}")
        return None

# Example usage (for testing within this file)
if __name__ == "__main__":
    # Example pricing (could come from a config file like pricing.json)
    try:
        with open("pricing.json", "r") as f:
            pricing_config = json.load(f)
            price_per_nft = pricing_config.get("price_ada", 3.0) # Default to 3 ADA if not found
    except FileNotFoundError:
        print("pricing.json not found, using default price of 3 ADA.")
        price_per_nft = 3.0
    except json.JSONDecodeError:
        print("Error reading pricing.json, using default price of 3 ADA.")
        price_per_nft = 3.0

    num_nfts_to_mint = 5

    print(f"Testing PaymentAgent (simulation) for {num_nfts_to_mint} NFTs at {price_per_nft} ADA each:")

    payment_info = initiate_masumi_payment(num_nfts_to_mint, price_per_nft)

    if payment_info:
        print("\nAgent Run Simulation Result (Payment Info):")
        print(json.dumps(payment_info, indent=2))
    else:
        print("\nAgent Run Simulation Failed.")

    # How the agent might actually run:
    # prompt = f"Initiate payment for a job minting {num_nfts_to_mint} NFTs."
    # response = payment_agent.run(prompt)
    # print("\nActual Agent Response (Conceptual):")
    # print(response) 