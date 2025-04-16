import streamlit as st
import requests # Added for API calls
import json # Added for handling response

st.title("Agno NFT Creator Agent")

st.header("Create Your NFT Collection")

# Define backend URL (adjust if your backend runs elsewhere)
BACKEND_URL = "http://127.0.0.1:8000"

with st.form("nft_creation_form"):
    collection_name = st.text_input("Collection Name", "")
    creative_prompt = st.text_area("Creative Prompt (Optional - AI will generate images if left blank)", "")
    wallet_address = st.text_input("Your Cardano Wallet Address", "")
    # Placeholder for asset upload (can be added later if needed)
    # uploaded_files = st.file_uploader("Upload Assets (Optional)", accept_multiple_files=True)

    submitted = st.form_submit_button("Start NFT Creation Job")

    if submitted:
        st.write(f"Submitting job for collection: {collection_name}...")
        st.write(f"Wallet Address: {wallet_address}")
        if creative_prompt:
            st.write(f"Using creative prompt: {creative_prompt}")
        else:
            st.write("No prompt provided, AI will generate images.")

        # Prepare data for backend
        payload = {
            "collection_name": collection_name,
            "creative_prompt": creative_prompt if creative_prompt else None,
            "wallet_address": wallet_address,
            # "uploaded_files": None # TODO: Handle actual file uploads if implemented
        }

        start_job_endpoint = f"{BACKEND_URL}/start_job"

        try:
            response = requests.post(start_job_endpoint, json=payload)
            response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)

            # Display success message and response from backend
            st.success("Job submitted successfully!")
            try:
                response_data = response.json()
                st.json(response_data) # Display the JSON response
            except json.JSONDecodeError:
                st.text(response.text) # Display raw text if not JSON

        except requests.exceptions.ConnectionError:
            st.error(f"Failed to connect to the backend at {start_job_endpoint}. Is it running?")
        except requests.exceptions.RequestException as e:
            st.error(f"Error submitting job: {e}")
            # Display error details from response if available
            try:
                error_details = response.json()
                st.json(error_details)
            except (AttributeError, json.JSONDecodeError):
                st.text(response.text if 'response' in locals() else "No response text available.") 