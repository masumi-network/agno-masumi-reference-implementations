# Agno Masumi Agent Collection

A collection of AI agent services that integrate with the Masumi payment system on the Cardano blockchain to provide monetized AI capabilities.

## Overview

This repository contains multiple specialized AI agents, each designed to perform specific tasks while leveraging the Masumi payment infrastructure for monetization.

## Agents

### Completed Agents

1. **agno_nft_agent** ✅
   - Generates AI art and mints it as NFTs on the Cardano blockchain
   - Supports both image and video generation
   - Handles NFT minting and transfer to customer wallets

### Agents In Development

2. **agno_llm_txt_agent** 🚧
   - Text generation capabilities using Large Language Models
   - Content generation for various purposes

3. **agno_crypto_report** 🚧
   - Cryptocurrency market analysis and reporting
   - Custom insights on crypto projects

4. **agno_data_analyst** 🚧
   - Data analysis and visualization
   - Insights generation from structured data

5. **agno_lawyer_agent** 🚧
   - Legal document analysis and generation
   - Contract review assistance

6. **agno_seo_agent** 🚧
   - SEO optimization recommendations
   - Content analysis for search visibility

7. **agno_trip_planner** 🚧
   - Travel itinerary generation
   - Trip recommendations based on preferences

## General Architecture

Each agent follows a similar architecture:
- FastAPI backend with MIP-003 compliant endpoints
- Integration with Masumi payment system
- Agent-specific AI capabilities defined in `agent_definition.py`
- Common logging and configuration utilities

## Setup Requirements

### Prerequisites

- Python 3.10 or higher
- Cardano wallet (for receiving payments)
- Masumi API credentials
- OpenAI API key

### Environment Setup

1. Create a virtual environment:
   ```bash
   cd agno_nft_agent  # Or other agent directory
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Create a `.env` file with the following variables:
   ```
   # OpenAI API Key
   OPENAI_API_KEY=your_openai_api_key

   # Masumi Payment Service
   PAYMENT_SERVICE_URL=https://payment.masumi.network/api/v1
   PAYMENT_API_KEY=your_masumi_payment_api_key
   NETWORK=PREPROD  # Or MAINNET for production

   # Agent Configuration
   AGENT_IDENTIFIER=your_agent_identifier_from_masumi
   PAYMENT_AMOUNT=10000000  # Amount in lovelace (10 ADA)
   PAYMENT_UNIT=lovelace
   SELLER_VKEY=your_cardano_verification_key
   ```

## Running an Agent

Navigate to the desired agent directory and start the API server:

```bash
cd agno_nft_agent  # Or other agent directory
python main.py api
```

The server will be available at http://localhost:8000. Visit http://localhost:8000/docs for interactive Swagger documentation.

## Troubleshooting Masumi Integration

### Common Issues

1. **"network: Required" error**:
   - Ensure NETWORK is set to "PREPROD" (all caps) in your .env file
   - Verify the PAYMENT_SERVICE_URL includes "/api/v1"
   - Confirm your Masumi API key is correctly set

2. **F-string Syntax Error**:
   - If you see errors about f-strings with nested quotes, ensure you're using Python 3.10+
   - Use single quotes inside f-strings with double quotes

3. **Payment Connection Issues**:
   - Check network connectivity to payment.masumi.network
   - Verify your AGENT_IDENTIFIER is correctly registered with Masumi

4. **Python Version Compatibility**:
   - Different Python versions handle some syntax differently
   - Python 3.12.8 is recommended for optimal compatibility

## Development Guidelines

When developing a new agent:

1. Use the existing agent structure as a template
2. Maintain MIP-003 compliance for all API endpoints
3. Keep the same environment variable structure
4. Handle payment status monitoring consistently
5. Implement proper error handling and logging

## Contributing

To contribute a new agent:

1. Clone the template from a working agent
2. Implement the specific agent capabilities
3. Test the integration with Masumi
4. Update the agent's README with specific details

## License

Proprietary - All rights reserved
