from crewai import Agent, Task, Crew, LLM
from crewai.process import Process
from crewai_tools import SerperDevTool
import os
import dotenv
from datetime import datetime
dotenv.load_dotenv()


class MeetingPreparationAgent:
    def __init__(
        self,
        openai_api_key: str | None = None,
        serper_api_key: str | None = None,
        model: str = "gpt-4o",
        temperature: float = 0.7,
        verbose: bool = True,
        process: Process = Process.sequential,
    ):
        """
        Initialize the MeetingPreparationAgent.
        API keys will be read from environment variables if not provided.
        """
        # Set API keys from parameters or environment variables
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        self.serper_api_key = serper_api_key or os.getenv("SERPER_API_KEY")
        
        if not self.openai_api_key:
            raise ValueError("OpenAI API key not provided")
        if not self.serper_api_key:
            raise ValueError("Serper API key not provided")
            
        # Set environment variables for the tools to use
        os.environ["SERPER_API_KEY"] = self.serper_api_key
        
        # Initialize the LLM and search tool
        self.llm = LLM(model=model, temperature=temperature, api_key=self.openai_api_key)
        self.search_tool = SerperDevTool()
        # Store verbosity and process configuration
        self.verbose = verbose
        self.process = process
        
    def prepare_meeting(self, company_name, meeting_objective, attendees, meeting_duration=60, focus_areas="", reference_links=None):
        """
        Prepare a comprehensive meeting package using AI agents.
        
        Args:
            company_name (str): Name of the company for the meeting
            meeting_objective (str): Main objective of the meeting
            attendees (str): List of attendees and their roles (one per line)
            meeting_duration (int): Meeting duration in minutes (default: 60)
            focus_areas (str): Specific areas of focus or concerns
            reference_links (list): Optional list of reference links to include in the preparation
            
        Returns:
            str: The final meeting preparation package as markdown text
        """
        # Define the agents with the search tool
        tools = [self.search_tool]
        
        context_analyzer = Agent(
            role='Meeting Context Specialist',
            goal='Analyze and summarize key background information for the meeting',
            backstory='You are an expert at quickly understanding complex business contexts and identifying critical information.',
            verbose=self.verbose,
            allow_delegation=False,
            llm=self.llm,
            tools=tools
        )

        industry_insights_generator = Agent(
            role='Industry Expert',
            goal='Provide in-depth industry analysis and identify key trends',
            backstory='You are a seasoned industry analyst with a knack for spotting emerging trends and opportunities.',
            verbose=self.verbose,
            allow_delegation=False,
            llm=self.llm,
            tools=tools
        )

        strategy_formulator = Agent(
            role='Meeting Strategist',
            goal='Develop a tailored meeting strategy and detailed agenda',
            backstory='You are a master meeting planner, known for creating highly effective strategies and agendas.',
            verbose=self.verbose,
            allow_delegation=False,
            llm=self.llm,
            tools=tools
        )

        executive_briefing_creator = Agent(
            role='Communication Specialist',
            goal='Synthesize information into concise and impactful briefings',
            backstory='You are an expert communicator, skilled at distilling complex information into clear, actionable insights.',
            verbose=self.verbose,
            allow_delegation=False,
            llm=self.llm,
            tools=tools
        )

        # Prepare reference links section for task descriptions
        reference_links_text = ""
        if reference_links:
            reference_links_text = "\n\nReference Links to analyze using the search tool:\n"
            for i, link in enumerate(reference_links, 1):
                reference_links_text += f"{i}. {link}\n"

        # Define the tasks
        context_analysis_task = Task(
            description=f"""
            Analyze the context for the meeting with {company_name}, considering:
            1. The meeting objective: {meeting_objective}
            2. The attendees: {attendees}
            3. The meeting duration: {meeting_duration} minutes
            4. Specific focus areas or concerns: {focus_areas}

            Research {company_name} thoroughly, including:
            1. Recent news and press releases
            2. Key products or services
            3. Major competitors
            4. Financial performance and market position
            5. Historical context and previous interactions
            6. SWOT analysis
            7. Potential partnerships and collaborations
            8. Technological trends and innovations
            9. Regulatory landscape and compliance issues
            {reference_links_text}

            Use the search tool to find information about {company_name} and the reference links provided.

            Ensure all information included is verified and accurate. Do not include any information unless you are 100% sure of its validity.
            
            Provide a comprehensive summary of your findings, highlighting the most relevant information for the meeting context.
            Format your output using markdown with appropriate headings and subheadings.
            Include relevant links to sources where appropriate.
            """,
            agent=context_analyzer,
            expected_output="A detailed analysis of the meeting context and company background, including recent developments, financial performance, and relevance to the meeting objective, formatted in markdown with headings and subheadings. Include relevant links to sources and insights from searched website content."
        )

        industry_analysis_task = Task(
            description=f"""
            Based on the context analysis for {company_name} and the meeting objective: {meeting_objective}, provide an in-depth industry analysis:
            1. Identify key trends and developments in the industry
            2. Analyze the competitive landscape
            3. Highlight potential opportunities and threats
            4. Provide insights on market positioning
            5. Explore regulatory and economic factors affecting the industry
            6. Technological trends and innovations
            7. Partnership opportunities and strategic alliances
            {reference_links_text}

            Use the search tool to find industry information related to {company_name} and the reference links provided.

            Ensure the analysis is relevant to the meeting objective and attendees' roles. Verify all information for accuracy and do not include any unverified data.
            Format your output using markdown with appropriate headings and subheadings.
            Include relevant links to industry reports, competitor websites, and other resources.
            """,
            agent=industry_insights_generator,
            expected_output="A comprehensive industry analysis report, including trends, competitive landscape, opportunities, threats, and relevant insights for the meeting objective, formatted in markdown with headings and subheadings. Include hyperlinks to relevant sources and data points."
        )

        strategy_development_task = Task(
            description=f"""
            Using the context analysis and industry insights, develop a tailored meeting strategy and detailed agenda for the {meeting_duration}-minute meeting with {company_name}. Include:
            1. A time-boxed agenda with clear objectives for each section
            2. Key talking points for each agenda item
            3. Suggested speakers or leaders for each section
            4. Potential discussion topics and questions to drive the conversation
            5. Strategies to address the specific focus areas and concerns: {focus_areas}
            6. Contingency plans for potential challenges
            7. Visual aids and data presentations
            8. Detailed action plans and timelines
            {reference_links_text}

            Ensure the strategy and agenda align with the meeting objective: {meeting_objective}. Verify all information and ensure accuracy before inclusion.
            Format your output using markdown with appropriate headings and subheadings.
            Include links to any relevant resources, tools, or documents that might be useful during the meeting.
            """,
            agent=strategy_formulator,
            expected_output="A detailed meeting strategy and time-boxed agenda, including objectives, key talking points, and strategies to address specific focus areas, formatted in markdown with headings and subheadings. Include links to relevant resources where appropriate."
        )

        executive_brief_task = Task(
            description=f"""
            Synthesize all the gathered information into a comprehensive yet concise executive brief for the meeting with {company_name}. Create the following components:

            1. A detailed one-page executive summary including:
               - Clear statement of the meeting objective
               - List of key attendees and their roles
               - Critical background points about {company_name} and relevant industry context
               - Top 3-5 strategic goals for the meeting, aligned with the objective
               - Brief overview of the meeting structure and key topics to be covered

            2. An in-depth list of key talking points, each supported by:
               - Relevant data or statistics
               - Specific examples or case studies
               - Connection to the company's current situation or challenges
               - Links to supporting resources or references

            3. Anticipate and prepare for potential questions:
               - List likely questions from attendees based on their roles and the meeting objective
               - Craft thoughtful, data-driven responses to each question
               - Include any supporting information or additional context that might be needed
               - Link to detailed resources for further exploration

            4. Strategic recommendations and next steps:
               - Provide 3-5 actionable recommendations based on the analysis
               - Outline clear next steps for implementation or follow-up
               - Suggest timelines or deadlines for key actions
               - Identify potential challenges or roadblocks and propose mitigation strategies
               - Include links to tools, templates, or resources to support implementation
            {reference_links_text}

            Ensure the brief is comprehensive yet concise, highly actionable, and precisely aligned with the meeting objective: {meeting_objective}. Verify all information for accuracy and do not include any unverified data. The document should be structured for easy navigation and quick reference during the meeting.
            Format your output using markdown with appropriate headings and subheadings.
            Include hyperlinks to all relevant resources, reports, and references throughout the document.
            """,
            agent=executive_briefing_creator,
            expected_output="A comprehensive executive brief including summary, key talking points, Q&A preparation, and strategic recommendations, formatted in markdown with main headings (H1), section headings (H2), and subsection headings (H3) where appropriate. Use bullet points, numbered lists, emphasis (bold/italic) for key information, and hyperlinks to relevant resources throughout."
        )

        # Create the crew
        meeting_prep_crew = Crew(
            agents=[context_analyzer, industry_insights_generator, strategy_formulator, executive_briefing_creator],
            tasks=[context_analysis_task, industry_analysis_task, strategy_development_task, executive_brief_task],
            verbose=self.verbose,
            process=self.process
        )

        # Run the crew and return the result
        print("AI agents are preparing your meeting...")
        result = meeting_prep_crew.kickoff()
        return result

def main():
    """Simple command-line interface for the meeting preparation agent."""
    # Using predefined data instead of command-line arguments
    company = "Masumi Network"
    objective = "Besprechung von neuer Marketing von Sokosumi"
    attendees = """Patrick Tobler, CEO
Keanu Klestil, dev"""
    duration = 90
    focus = "Market expansion opportunities and competitive analysis"
    reference_links = [
        "https://masumi.network/about",
        "https://dev.sokosumi.com",
        "https://sokosumi.com",
        "https://masumi.network"
    ]
    
    try:
        agent = MeetingPreparationAgent()
        result = agent.prepare_meeting(
            company_name=company,
            meeting_objective=objective,
            attendees=attendees,
            meeting_duration=duration,
            focus_areas=focus,
            reference_links=reference_links
        )
        
        # Convert result to string if it's not already
        result_str = str(result)
        
        # Print the result
        print("\n\n" + "="*50)
        print("MEETING PREPARATION PACKAGE")
        print("="*50 + "\n")
        print(result_str)
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
