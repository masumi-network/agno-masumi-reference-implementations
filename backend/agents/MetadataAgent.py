# backend/agents/MetadataAgent.py

import json
from agno.agent import Agent
from agno.models.openai import OpenAIChat

# 🧾 MetadataAgent: Generates CIP-25 metadata
metadata_agent = Agent(
    name="MetadataAgent",
    model=OpenAIChat(id="gpt-4o"),
    description="Generates Cardano NFT metadata in CIP-25 format based on provided details and asset URIs.",
    instructions=[
        "Receive NFT collection details: collection name, description (optional), publisher (optional), royalties (optional).",
        "Receive a dictionary mapping original asset filenames/URLs to their IPFS URIs.",
        "Generate CIP-25 compliant JSON metadata for EACH asset URI provided.",
        "The metadata for each NFT should include at minimum: 'name', 'image' (the IPFS URI), and 'mediaType'.",
        "Use the original asset key (from the input dictionary) to infer the base 'name' for each NFT if needed (e.g., derive 'MyNFT_1' from 'image1.png').",
        "Ensure the 'image' field is the full IPFS URI (e.g., 'ipfs://Qm...').",
        "Structure the output STRICTLY as a JSON list of objects, where each object is the metadata for one NFT.",
        "CRITICAL: Your entire response MUST be ONLY the JSON list (starting with '[' and ending with ']') and NOTHING else. Do NOT include any introductory text, explanations, notes, comments, placeholders like '<policy_id>', or markdown formatting like ```json."
    ],
    markdown=True,
    # verbose=True # Optional: for debugging
)

# Example usage (for testing within this file)
if __name__ == "__main__":
    test_collection_details = {
        "collection_name": "Otherworlds",
        "description": "Dreamlike forests from another dimension.",
        # "publisher": "My Studio",
        # "royalties": "10%"
    }
    test_asset_mapping = {
        "image1.png": "ipfs://QmPlaceholderHashFor_image1.png",
        "image2.jpg": "ipfs://QmPlaceholderHashFor_image2.jpg"
    }

    print("Testing MetadataAgent with sample data:")
    print("Collection Details:", test_collection_details)
    print("Asset Mapping:", test_asset_mapping)

    # Constructing the input prompt for the agent
    prompt = f"""
    Generate CIP-25 metadata for the following NFT collection:
    Collection Details: {json.dumps(test_collection_details)}
    Asset IPFS URIs: {json.dumps(test_asset_mapping)}
    Generate metadata for each asset listed.
    """

    print("\nAgent Input Prompt:")
    print(prompt)

    # Running the agent
    # Note: Ensure OPENAI_API_KEY is set in the environment
    try:
        response = metadata_agent.run(prompt)
        print("\nAgent Response (Metadata JSON List):")
        # Attempt to parse the response as JSON for validation
        try:
            metadata_list = json.loads(response)
            print(json.dumps(metadata_list, indent=2))
        except json.JSONDecodeError:
            print("Error: Agent response is not valid JSON.")
            print(response)
    except Exception as e:
        print(f"An error occurred during agent execution: {e}") 