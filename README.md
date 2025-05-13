# Agno Masumi Agent Collection

A collection of specialized AI agents integrated with the Masumi.

## Overview

This repository contains multiple AI agents that provide monetized services through the Masumi payment infrastructure.

## Available Agents

| Agent | Repository | Status | Description |
|-------|------------|--------|-------------|
| **agno_nft_agent** | [Repository](https://github.com/masumi-network/agno-masumi-reference-implementations/tree/main/agno_llm_txt_agent) | ✅ Live | Generates AI art and mints NFTs on Cardano |
| **agno_llm_txt_agent** | [Repository](https://github.com/masumi-network/agno-masumi-reference-implementations/tree/main/agno_llm_txt_agent) | ✅ Live | Text generation using LLMs; website content extraction |
| **agno_finance_report_agent** | [Repository](https://github.com/masumi-network/agno-masumi-reference-implementations/tree/main/agno_finance_report_agent) | 🚧 Beta | Comprehensive cryptocurrency market analysis |
| **agno_data_analyst** | [Repository](https://github.com/masumi-network/agno-masumi-reference-implementations/tree/main/agno_data_analyst) | 🚧 Beta | Data analysis and visualization services |
| **agno_lawyer_agent** | [Repository](https://github.com/masumi-network/agno-masumi-reference-implementations/tree/main/agno_lawyer_agent) | 🚧 Beta | Legal document analysis and generation |
| **agno_seo_agent** | [Repository](https://github.com/masumi-network/agno-masumi-reference-implementations/tree/main/agno_seo_agent) | ✅ Live | SEO optimization and content analysis |
| **agno_trip_planner** | [Repository](https://github.com/masumi-network/agno-masumi-reference-implementations/tree/main/agno_trip_planner) | 🚧 Beta | Travel itinerary generation and recommendations |

All agents are available on [sokosumi Marketplace](https://sokosumi.com)

## Architecture

- FastAPI backend with MIP-003 compliant endpoints
- Masumi payment system integration
- Agent-specific capabilities in `agent_definition.py`
- Common utilities for logging and configuration

## Setup Requirements

### Prerequisites

- Python 3.10+
- Cardano wallet
- Masumi API credentials
- OpenAI API key

### Environment Setup

1. Create a virtual environment:
   ```bash
   cd agent_directory
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Configure `.env` file:
   ```
   OPENAI_API_KEY=your_openai_api_key
   PAYMENT_SERVICE_URL=https://payment.masumi.network/api/v1
   PAYMENT_API_KEY=your_masumi_payment_api_key
   NETWORK=PREPROD  # or MAINNET
   AGENT_IDENTIFIER=your_agent_identifier
   PAYMENT_AMOUNT=10000000  # in lovelace
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

MIT License

Copyright (c) 2025 Masumi

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
