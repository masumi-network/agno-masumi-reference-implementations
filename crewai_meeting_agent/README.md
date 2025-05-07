# Meeting Preparation Agent

The Meeting Preparation Agent is designed to assist in preparing comprehensive meeting packages using AI agents. It leverages various tools and APIs to gather and analyze information, providing detailed insights and strategies for effective meetings.

## Features

- **Context Analysis**: Analyzes the meeting context, including company background, recent developments, and relevant industry insights.
- **Industry Analysis**: Provides in-depth analysis of industry trends, competitive landscape, and potential opportunities.
- **Strategy Development**: Develops a tailored meeting strategy and agenda, including key talking points and discussion topics.
- **Executive Briefing**: Synthesizes information into a concise executive brief, including strategic recommendations and next steps.

## Usage

The agent can be used via a simple command-line interface. It requires API keys for OpenAI, Serper, and Firecrawl, which can be set as environment variables or passed directly to the agent.

### Example

```python
from agent_definition import MeetingPreparationAgent

agent = MeetingPreparationAgent(
    openai_api_key='your_openai_api_key',
    serper_api_key='your_serper_api_key',
    firecrawl_api_key='your_firecrawl_api_key'
)

result = agent.prepare_meeting(
    company_name="Masumi",
    meeting_objective="Discuss new marketing strategies for Sokosumi",
    attendees="Patrick Tobler, CEO\nKeanu Klestil, CTO\nPhil, Sales Director\nFlo, Product Manager",
    meeting_duration=90,
    focus_areas="Market expansion opportunities and competitive analysis",
    reference_links=[
        "https://masumi.network/about",
        "https://dev.sokosumi.com",
        "masumi.network"
    ]
)

print(result)
```

## Requirements

- Python 3.x
- `crewai`, `crewai_tools`, and other dependencies as specified in `requirements.txt`

## Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   ```
2. Install the required packages:
   ```bash
   pip install -r requirements.txt
   ```

## License

This project is licensed under the MIT License.
