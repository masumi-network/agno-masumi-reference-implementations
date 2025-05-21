from textwrap import dedent
from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.tools.yfinance import YFinanceTools
from agno.tools.firecrawl import FirecrawlTools
from agno.tools.exa import ExaTools
from agno.tools.googlesearch import GoogleSearchTools
from dotenv import load_dotenv
import os
import json
import asyncio
import time
import logging
import random
from functools import wraps
import subprocess # Added
import boto3 # Added
from botocore.exceptions import NoCredentialsError, ClientError # Added

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Configure API keys
FirecrawlTools.api_key = os.getenv("FIRECRAWL_API_KEY")
ExaTools.api_key = os.getenv("EXA_API_KEY")
OpenAIChat.api_key = os.getenv("OPENAI_API_KEY")

# Rate limiting decorator
def rate_limit(max_per_second=1, max_burst=3):
    """
    Decorator to rate limit function calls
    
    Args:
        max_per_second: Maximum calls per second
        max_burst: Maximum burst of calls allowed
    """
    min_interval = 1.0 / max_per_second
    last_called = [0.0]
    tokens = [max_burst]
    
    def decorate(func):
        @wraps(func)
        async def wrapped(*args, **kwargs):
            current_time = time.time()
            elapsed = current_time - last_called[0]
            
            # Add tokens based on elapsed time
            new_tokens = elapsed * max_per_second
            tokens[0] = min(max_burst, tokens[0] + new_tokens)
            
            if tokens[0] < 1:
                # Not enough tokens, sleep until we have one
                sleep_time = (1 - tokens[0]) / max_per_second
                logger.info(f"Rate limiting: sleeping for {sleep_time:.2f}s for {func.__name__}")
                await asyncio.sleep(sleep_time)
                tokens[0] = 1
            
            # Use a token and update last_called
            tokens[0] -= 1
            last_called[0] = time.time()
            
            # Add jitter to avoid synchronized requests
            jitter = random.uniform(0, 0.2) # Reduced jitter slightly
            await asyncio.sleep(jitter)
            
            # Execute function with retry on rate limit errors
            max_retries = 3
            retry_count = 0
            
            while retry_count < max_retries:
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    if "429" in str(e) or "rate limit" in str(e).lower():
                        retry_count += 1
                        wait_time = (2 ** retry_count) * min_interval + random.uniform(0, 1) # Exponential backoff based on interval
                        logger.warning(f"Rate limit hit for {func.__name__}, retrying in {wait_time:.2f}s (attempt {retry_count}/{max_retries})")
                        await asyncio.sleep(wait_time)
                    else:
                        # If it's not a rate limit error, re-raise
                        logger.error(f"Error in {func.__name__}: {str(e)}")
                        return f"Error retrieving data via {func.__name__}: {str(e)}"
            
            return f"Unable to complete request via {func.__name__} due to rate limiting after multiple retries"
        
        return wrapped
    
    return decorate

# Create a sequential rate-limited Exa search function
@rate_limit(max_per_second=0.7, max_burst=1) # Further adjusted Exa rate limit for safety
async def rate_limited_exa_search(agent, query):
    """Execute Exa search with rate limiting"""
    result = await agent.arun(query)
    # Extract string content if it's a RunResponse object
    return result.content if hasattr(result, 'content') else str(result)

# Rate limited Google search
@rate_limit(max_per_second=1.0, max_burst=2) # Further adjusted Google rate limit
async def rate_limited_google_search(agent, query):
    """Execute Google search with rate limiting"""
    result = await agent.arun(query)
    # Extract string content if it's a RunResponse object
    return result.content if hasattr(result, 'content') else str(result)

# 1. Define specialized sub-agents with more focused tasks to reduce API calls

# Financial Data Agent - Focuses on core financial metrics
financial_data_agent = Agent(
    model=OpenAIChat(id="gpt-4o"),
    tools=[
        YFinanceTools(
            stock_price=True,
            analyst_recommendations=True,
            stock_fundamentals=True,
            historical_prices=True,
            company_info=True,
            income_statements=True,
            key_financial_ratios=True,
            technical_indicators=True,
        ),
    ],
    instructions=dedent("""\
        You are a quantitative financial data specialist. Your output will be consumed by a synthesis agent to write an EXTREMELY detailed, data-heavy report.
        Your task is to provide an **ULTRA-DETAILED JSON output**. For EACH company/ticker specified:
        1.  **Current Market Data (Exhaustive):** Current Price, Previous Close, Open, Bid, Ask, Day's Range, 52-Week Range, Volume, Average Volume (3 month), Market Cap, Beta (5Y Monthly), PE Ratio (TTM), EPS (TTM), Forward Dividend & Yield, Ex-Dividend Date, 1y Target Est. Provide every available numerical figure.
        2.  **Historical Price Analysis (Daily for past 1 year, Weekly for past 5 years if available):** Date, Open, High, Low, Close, Adjusted Close, Volume. Identify key S&R levels with dates.
        3.  **In-depth Technical Indicators (Calculated Values & Interpretation):**
            *   Moving Averages: 20-day, 50-day, 100-day, 200-day SMA & EMA values. State if price is above/below and interpret signal (bullish/bearish).
            *   RSI (14-day): Current value. Interpretation (e.g., "75 - Overbought, potential pullback"). Historical RSI peaks/troughs.
            *   MACD (12, 26, 9): MACD line value, Signal line value, Histogram value. Dates of recent bullish/bearish crossovers and their significance.
            *   Bollinger Bands (20-day, 2 SD): Upper band value, middle band value, lower band value. Current price relation to bands (e.g., "Price testing upper band, potential volatility").
            *   Stochastic Oscillator (14, 3, 3): %K, %D values. Interpretation (overbought/oversold).
            *   Volume Profile (if inferable or data available): Key high-volume nodes.
        4.  **Comprehensive Financial Statement Summaries (Quarterly for last 8-12 quarters, Annually for last 5-7 years, with ALL LINE ITEMS available from YFinance):**
            *   Income Statement: Revenue, Cost of Revenue, Gross Profit, R&D, SG&A, Other Operating Expenses, Operating Income (EBIT), Interest Expense, Income Before Tax, Income Tax Expense, Net Income from Continuing Ops, Net Income, EPS (Basic & Diluted). Include YoY and QoQ growth percentages for ALL key line items.
            *   Balance Sheet: ALL Assets (Cash, Short Term Investments, Net Receivables, Inventory, Other Current Assets, Total Current Assets; Long Term Investments, Property Plant Equipment, Goodwill, Intangible Assets, Other Assets, Total Assets). ALL Liabilities (Accounts Payable, Short Long Term Debt, Other Current Liabilities, Total Current Liabilities; Long Term Debt, Other Liabilities, Deferred Long Term Liability Charges, Total Liabilities). ALL Equity (Common Stock, Retained Earnings, Treasury Stock, Capital Surplus, Other Stockholder Equity, Total Stockholder Equity). Key Ratios derived (e.g., Debt-to-Equity).
            *   Cash Flow Statement: ALL line items for Operating, Investing, and Financing activities. Net Income, Depreciation, Changes in Working Capital components, Capital Expenditures, Issuance/Repurchase of Stock, Issuance/Repayment of Debt, Dividends Paid. Free Cash Flow (FCF) calculation shown.
        5.  **Exhaustive Key Financial Ratios (Calculated for EACH of the last 5-7 years and EACH of the last 4-8 quarters):**
            *   Profitability: Gross Profit Margin, Operating Profit Margin, Net Profit Margin, Return on Assets (ROA), Return on Equity (ROE), Return on Invested Capital (ROIC).
            *   Liquidity: Current Ratio, Quick Ratio (Acid Test), Cash Ratio.
            *   Solvency: Debt-to-Equity Ratio, Total Debt-to-Total Assets Ratio, Interest Coverage Ratio, Financial Leverage.
            *   Efficiency: Asset Turnover Ratio, Inventory Turnover (and Days), Accounts Receivable Turnover (and Days Sales Outstanding), Accounts Payable Turnover (and Days Payable Outstanding), Working Capital Turnover.
            *   Market Valuation: P/E (TTM & Forward), Price-to-Sales (P/S TTM), Price-to-Book (P/B MRQ), PEG Ratio (if applicable), Enterprise Value to EBITDA (EV/EBITDA TTM), Dividend Yield, Dividend Payout Ratio.
            *   For EACH ratio, provide its formula, the calculated value for each period, and a brief interpretation of the trend and its meaning (e.g., "ROE increased from 15% to 18%, indicating improved profitability from shareholder equity").
        6.  **Quantitative Risk Metrics:** Beta (5Y Monthly), Standard Deviation of daily returns (Annualized Volatility - 30D, 90D, 1Y), Sharpe Ratio (calculated using a stated assumed risk-free rate, e.g., current 10-year Treasury yield).
        7.  **Analyst Recommendations & Estimates (from YFinance):** Full breakdown of Strong Buy, Buy, Hold, Sell, Strong Sell ratings. Mean, Median, Low, High price targets. Earnings estimate trends (current quarter, next quarter, current year, next year). Revenue estimate trends.
        Ensure all data includes units and dates. The goal is maximum data density for the synthesis agent.
    """),
    markdown=True,
)

# News Agent - Focuses on recent news only
news_agent = Agent(
    model=OpenAIChat(id="gpt-4o"),
    tools=[GoogleSearchTools(fixed_max_results=12, fixed_language="en")], # Max results
    instructions=dedent("""\
        You are a financial news intelligence bloodhound. Your output is for an ultra-detailed synthesis report needing rich, specific information.
        Your task is to find and provide **EXCEPTIONALLY DETAILED** summaries of the latest and most impactful news for the specified companies/sectors, covering the **last 4-6 weeks**.
        Focus on:
        1.  **Corporate Announcements:** Earnings reports (quote specific revenue, EPS, guidance figures vs. analyst estimates; detail management commentary on each business segment). M&A (deal values, strategic rationale, expected synergies/impact, regulatory status). Partnerships (nature of partnership, expected benefits, key players). Major product launches (specific features, target market, pricing, initial reception). Leadership changes (reasons, impact). Significant financing rounds (amount, investors, use of proceeds).
        2.  **Market-Moving Events:** Specific macroeconomic data releases directly cited as impacting the company/sector. Documented significant stock price movements (>5-10% in a day/week) with multiple attributed reasons from financial news.
        3.  **Regulatory Developments:** Specific new laws, proposed regulations, ongoing investigations, significant fines, or crucial approvals/rejections by regulatory bodies. Quote agency names and specific regulation codes if possible.
        4.  **Competitive Intelligence:** Competitor earnings summaries (key figures), new product announcements by rivals, significant strategic shifts by competitors, documented market share changes or surveys.
        5.  **Industry-Wide News:** Updates on supply chain issues (quantify impact if possible), technological breakthroughs with company-specific implications, key takeaways from major industry conferences or influential reports.
        Provide a detailed JSON. Each news item **MUST** include:
            *   `source_url`: Direct link to the primary article.
            *   `publication_date`: Exact date (YYYY-MM-DD).
            *   `headline`: Original, full headline.
            *   `publication_name`: Name of the news outlet (e.g., Reuters, Bloomberg).
            *   `ultra_detailed_summary`: A multi-paragraph, highly specific summary. **Quote key figures, dates, names, and specific impacts mentioned in the article.** Do not generalize. Extract as much factual data as possible.
            *   `quantitative_impact_data`: A sub-object specifically listing any numbers, percentages, monetary values, or date ranges mentioned (e.g., {"revenue_guidance": "USD 1.2B - 1.3B", "stock_change_pct": -5.2, "target_date": "2025-Q4"}).
            *   `direct_quotes`: At least 2-3 impactful direct quotes from the article from key individuals or analysts.
            *   `analyst_commentary_summary`: If the article includes analyst commentary on the event, summarize it specifically.
        Aim for 10-15 significant, deeply detailed, and data-rich news items. Prioritize news with quantifiable information.
    """),
    markdown=True,
)

# Research Agent - Focuses on analyst reports using Exa
research_agent = Agent(
    model=OpenAIChat(id="gpt-4o"),
    tools=[
        ExaTools(
            search=True, get_contents=True, text=True, text_length_limit=5000, # Max length
            highlights=False, summary=False, num_results=8, # Max results, want raw text
            livecrawl="always", type="neural",
        ),
    ],
    instructions=dedent("""\
        You are a deep-dive financial research extraction specialist. Your output must provide extensive raw material for an ultra-detailed synthesis.
        Your task is to uncover and provide **EXTREMELY DETAILED insights and large verbatim excerpts** from professional analyst reports, white papers, academic research, and in-depth articles for the specified companies/sectors. **Prioritize fetching and returning as much of the original text content as possible.**
        Focus on:
        1.  **Recent Full Analyst Reports (last 6-12 months, try to find 3-5 distinct reports):**
            *   For EACH report:
            *   `source_details`: Investment Bank/Firm, Analyst Name(s), Publication Date, Report Title.
            *   `rating_and_price_target`: Explicit Rating (e.g., Buy, Outperform) and Price Target (e.g., USD 150.00) with the analyst's exact justification.
            *   `investment_thesis_summary`: A detailed multi-paragraph summary of their core investment argument, key assumptions, and logic.
            *   `key_catalysts_verbatim`: Directly quote sections describing key positive catalysts.
            *   `key_risks_verbatim`: Directly quote sections detailing key risks and concerns.
            *   `financial_model_assumptions_verbatim`: If the report details specific assumptions for revenue growth rates (e.g., "We model 15% YoY revenue growth for FY24"), margins, CapEx, or discount rates, quote these directly.
            *   `segment_analysis_verbatim`: Quote detailed analysis of specific business segments.
            *   `valuation_methodology_verbatim`: Quote how they arrived at their valuation (e.g., "Our PT is based on a 25x FY2 P/E multiple applied to our EPS estimate of $6.00").
            *   `extensive_key_excerpts`: Include several lengthy (multi-paragraph) direct quotes from the most insightful parts of the report.
        2.  **In-depth Industry Outlooks & Thematic Research (1-2 comprehensive pieces):**
            *   Extract long sections discussing broader industry trends, technological disruptions, competitive dynamics, or long-term thematic plays relevant to the company/sector. Include data tables or charts if described in text.
        3.  **Academic Papers or Specialized White Papers (1-2 relevant pieces):**
            *   If relevant (e.g., for tech or biotech), find papers discussing the underlying technology or scientific basis. Extract key findings, data, and conclusions.
        Provide a detailed JSON output. Each entry should be rich with **verbatim text and direct quotes**. The `extensive_summary_and_key_excerpts` field for each research piece should be very long and contain primarily directly extracted text. **Minimize your own summarization; maximize extraction of original detailed content.**
    """),
    markdown=True,
)

# ESG Agent - Focuses on environmental, social, governance aspects
esg_agent = Agent(
    model=OpenAIChat(id="gpt-4o"),
    tools=[GoogleSearchTools(fixed_max_results=10, fixed_language="en")], # Max results
    instructions=dedent("""\
        You are an ESG (Environmental, Social, Governance) and Sustainability data forensic investigator. Your analysis is for an ultra-detailed report requiring precise data.
        Your task is to conduct **EXHAUSTIVE** research and provide an **ULTRA-DETAILED, DATA-PACKED** analysis of ESG factors for the specified companies, referencing their latest sustainability reports, CDP disclosures, and reputable third-party ESG ratings/reports.
        Provide specific **NUMBERS, TARGETS, DATES, PERCENTAGES, and PERFORMANCE METRICS** for every point possible:
        1.  **Environmental (E) - Quantify Everything:**
            *   Climate Strategy & Governance: Stated carbon reduction targets (e.g., "Reduce Scope 1&2 by 50% by 2030 from a 2019 baseline"), net-zero commitments with dates, board committee responsible for climate, TCFD alignment status.
            *   Greenhouse Gas Emissions (Latest Full Year & Previous 2 Years): Scope 1 (tonnes CO2e), Scope 2 (market-based & location-based, tonnes CO2e), Scope 3 (categories reported, tonnes CO2e). Emission intensity (e.g., tonnes CO2e / $M revenue or per unit production).
            *   Energy: Total energy consumption (MWh or GJ), % renewable electricity, % renewable energy total. Energy efficiency projects implemented and savings achieved.
            *   Water: Total water withdrawal (m³), water consumption (m³), % water recycled/reused, water withdrawal in high-stress regions.
            *   Waste: Total waste generated (tonnes), % hazardous waste, % waste recycled, % waste diverted from landfill. Specific circular economy initiatives and material efficiency metrics.
            *   Biodiversity & Land Use: Policies, land use for operations, restoration projects, impact assessments.
            *   Environmental CAPEX/OPEX: Investments in environmental projects. Fines/penalties for environmental non-compliance.
        2.  **Social (S) - Quantify Everything:**
            *   Human Capital: Total employees, employee turnover rate (voluntary/involuntary), average training hours per employee, D&I statistics (e.g., % women in management, % ethnic minorities in workforce – provide actual numbers if available). Pay equity audit results. Employee engagement survey scores.
            *   Labor Practices & Human Rights: Lost Time Injury Frequency Rate (LTIFR), Total Recordable Incident Rate (TRIR). Supplier code of conduct details, % suppliers audited for labor practices. Human rights due diligence processes.
            *   Community Impact: Value of community investments/donations (USD), employee volunteering hours.
            *   Product Responsibility: Product recall instances/severity, customer satisfaction scores (e.g., NPS), data privacy policies, number of data breaches and individuals affected. Investment in R&D for safer/more sustainable products.
        3.  **Governance (G) - Detail Structure & Performance:**
            *   Board Structure: Total directors, % independent, average tenure, gender/ethnic diversity on board (actual numbers/percentages). Lead Independent Director? Chairman/CEO split? Board committee charters (Audit, Comp, Nom/Gov) – key responsibilities. Director attendance rates.
            *   Executive Compensation: Structure of CEO pay (salary, bonus, LTI). % of exec comp linked to ESG targets. Shareholder say-on-pay vote results (past 3 years). Clawback policy details.
            *   Shareholder Rights: Voting structure (e.g., dual-class shares?), proxy access provisions, shareholder proposal thresholds and history of ESG proposals.
            *   Business Ethics & Compliance: Details of code of conduct, anti-corruption training completion rates, whistleblower reports and outcomes. Fines/settlements for ethical/compliance breaches.
            *   Risk Management: How ESG risks are integrated into enterprise risk management.
            *   Transparency & Reporting: Specific frameworks used for sustainability reporting (GRI Standards, SASB, IFRS S1/S2, TCFD). External assurance provider and level of assurance for ESG data.
        4.  **Overall ESG Ratings & Performance (from multiple sources if possible):**
            *   MSCI ESG Rating: (e.g., AAA, AA, A, BBB, BB, B, CCC) - current and historical. Key positive/negative factors cited.
            *   Sustainalytics ESG Risk Rating: (e.g., Negligible, Low, Medium, High, Severe) - current score and risk category. Key material ESG issues identified.
            *   CDP Scores: Climate Change, Water Security, Forests scores (e.g., A, A-, B, C, D).
            *   Other relevant ratings (e.g., ISS, Refinitiv).
        Provide a minutely detailed JSON output. For EACH sub-point above, provide the specific data, numbers, targets, dates, and direct quotes from source documents. If data is unavailable for a specific point, explicitly state "Data not found in publicly available sources."
    """),
    markdown=True,
)

# Macroeconomic Agent - Focuses on industry-specific macro factors
macro_agent = Agent(
    model=OpenAIChat(id="gpt-4o"),
    tools=[GoogleSearchTools(fixed_max_results=10, fixed_language="en")], # Max results
    instructions=dedent("""\
        You are a global macroeconomic and geopolitical strategist. Your analysis forms a crucial part of an ultra-detailed investment report.
        Your task is to research and provide an **EXTREMELY DETAILED, DATA-RICH** analysis of macroeconomic and geopolitical factors pertinent to the specified industry/companies.
        For each point, provide **specific numbers, forecasts, dates, sources, and detailed explanations of the *IMPACT* on the company/industry.**
        1.  **Current & Projected Economic Indicators (Global & Key Operating Regions for the Company/Sector – e.g., US, China, EU):**
            *   Inflation (Latest month & YoY % change, forecasts for next 12-24 months): CPI, Core CPI, PPI. Key drivers (e.g., energy, food, wages). Central bank inflation targets. **Impact:** How does this affect the company's input costs, pricing power, consumer demand for its products/services, and borrowing costs?
            *   Interest Rates (Current central bank policy rates, 10-year government bond yields – current & 12m forecast): Federal Reserve, ECB, other relevant central banks. Forward guidance. **Impact:** How do current and expected rates affect the company's cost of capital, investment decisions, valuation multiples, and consumer financing for its products?
            *   GDP Growth (Latest quarter & YoY % change, forecasts for next 12-24 months): Real GDP. Key contributing sectors. Recession probabilities (cite sources like Bloomberg, IMF, World Bank). **Impact:** How does GDP growth correlate with demand for the company's offerings? How would a recession in key markets affect it?
            *   Unemployment & Labor Markets (Latest unemployment rate, wage growth % YoY): Labor force participation rate. Skills shortages or surpluses relevant to the industry. **Impact:** How does the labor market affect the company's hiring ability, labor costs, and consumer purchasing power?
        2.  **Significant Regulatory & Policy Landscapes (Specific to Industry & Company):**
            *   Detail 3-5 specific existing or proposed national/international regulations (e.g., US Inflation Reduction Act provisions for EVs, EU AI Act, China's data security laws) that directly impact the company/industry. Explain their mechanisms and **quantify potential financial or operational impacts (e.g., "could add $X million in compliance costs" or "provides Y% tax credit for Z").**
            *   Government stimulus, subsidies, tax incentives, or industrial policies directly benefiting or harming the sector (provide specific program names and values).
            *   Antitrust and competition policy developments.
        3.  **Major Geopolitical Events, Tensions & Alliances (Current & Developing):**
            *   Analyze 2-3 specific ongoing geopolitical situations (e.g., Russia-Ukraine, US-China relations, regional conflicts) and their **direct and indirect impacts on the company/industry's supply chains, market access, input costs, and investor sentiment.**
            *   Impact of major international trade agreements, sanctions, or tariffs relevant to the company's operations or markets.
            *   Country-specific political risk assessment for key operational or market geographies.
        4.  **Supply Chain Dynamics & Commodity Markets (Specific to Industry Inputs):**
            *   Identify 3-5 critical raw materials, components, or energy sources for the industry. Analyze their current price trends (e.g., % change YoY, 5-year charts if possible), supply/demand outlook, and key producing regions. **How do these affect the company's COGS and production capacity?**
            *   Analysis of key global supply chain vulnerabilities, bottlenecks (e.g., semiconductor shortages, port congestion), and resilience strategies being adopted by the industry.
            *   Logistics and transportation costs (e.g., shipping rates) and their trends.
        5.  **Long-Term Secular Trends & Structural Shifts (Quantify where possible):**
            *   Demographic shifts (e.g., aging population, urbanization in key markets) and their impact on product demand, labor force, and consumer preferences relevant to the company over the next 5-10 years.
            *   Pervasive technological shifts (AI, IoT, automation, digitalization, Web3 for crypto) – **specific adoption rates, market size forecasts for these tech segments, and how the company is positioned.**
            *   Climate change physical and transition risks/opportunities relevant to the industry (e.g., cost of carbon, demand for green tech).
            *   Shifts in consumer behavior (e.g., e-commerce penetration, subscription models, sustainability preferences).
        Provide a minutely detailed JSON output. Each factor must have extensive, data-supported analysis. For every claim or trend, cite where the data/forecast is from if it's a public source (e.g., "according to the IMF's latest WEO...").
    """),
    markdown=True,
)


# --- MODULAR SYNTHESIS AGENTS ---
_synthesis_agent_common_instructions = dedent("""\
    You are a Chief Investment Strategist at a prestigious Wall Street firm, crafting a specific PART of an **ULTRA-COMPREHENSIVE, EXCEPTIONALLY DETAILED, DATA-SATURATED, INSTITUTIONAL-GRADE** investment research report. This entire report aims for 25-40+ pages (60,000 - 100,000+ characters). Your assigned PART must reflect this ambition in its depth and length.

    **ABSOLUTE CORE MANDATE FOR YOUR ASSIGNED PART: FORENSIC DATA INTEGRATION & EXTREME ELABORATION**
    For **EVERY SINGLE RELEVANT NUMERICAL DATA POINT, STATISTIC, FINANCIAL RATIO, DATE, MONETARY VALUE, PERCENTAGE, TARGET, RATING, and FORECAST** from the **TOTAL PROVIDED SUB-AGENT JSON INPUTS** that pertains to **YOUR ASSIGNED SECTIONS ONLY**, you **MUST** perform the following with painful, exhaustive detail:
    1.  **Explicitly Quote & Attribute:** State the precise data point/finding (e.g., "The `financial_data_agent` reported a Q3 EPS for [Company] of $1.25...").
    2.  **Define & Contextualize:** Clearly define the metric. Provide deep context: What does this number mean? What is its historical trend (e.g., "This $1.25 EPS is up from $1.10 in Q2 and $0.95 in Q3 last year, showing an X% QoQ and Y% YoY growth...")? How does it compare to direct competitors (e.g., "...significantly above Competitor A's $1.05 EPS...")? How does it compare to analyst expectations or company guidance?
    3.  **Analyze Implications (Multi-Paragraph):** What are the profound short-term and long-term implications of this specific number for the company's financial health, operational efficiency, market position, growth prospects, and stock valuation, *specifically within the context of your assigned sections*?
    4.  **Elaborate Massively:** Write **multiple, dense paragraphs** expanding on each significant data point relevant to your sections. Use supporting arguments, connect it to other relevant data points from different sub-agent inputs.
    5.  **Integrate into Narrative:** Seamlessly weave this granular data analysis into a flowing, cohesive narrative for your assigned sections. The numbers must tell a story.
    6.  **Critical Lens:** If data pertinent to your sections seems contradictory or raises questions, discuss these complexities.

    **IMPORTANT: LATEX COMPATIBILITY & MARKDOWN FORMATTING FOR PDF CONVERSION**
    The final Markdown report will be converted to PDF using Pandoc and LaTeX. To minimize conversion errors:
    *   **Mathematical Formulas:**
        *   For **display mathematics** (formulas on their own line, centered), use `$$ ... $$` delimiters. Example: `$$ E = mc^2 $$`
        *   For **inline mathematics** (formulas within a paragraph), use `$ ... $` delimiters. Example: `The return is $R_i = \alpha_i + \beta_i R_m + \epsilon_i$.`
        *   Ensure all mathematical symbols and LaTeX commands (e.g., `\times`, `\Delta`, `\sum`, `\frac{}{}`, `\text{...}`, `\alpha`, `\beta`) are correctly placed *inside* these math delimiters.
        *   Avoid using `\[ ... \]` or `\( ... \)` for math, as `$$...$$` and `$...$` are generally more robust with Pandoc for LaTeX output.
    *   **Special Characters in Plain Text:** Be very cautious with characters that have special meaning in LaTeX when they appear in regular text (i.e., outside of code blocks or math environments). These include: `_` (underscore), `^` (caret), `\` (backslash), `{ }` (curly braces), `$` (dollar sign), `%` (percent sign), `#` (hash/pound sign), `&` (ampersand).
        *   If an underscore `_` is needed in plain text (e.g., a variable_name not in code or math), it will likely cause a LaTeX error or be misinterpreted. If essential, it might need to be escaped as `\_` in the final LaTeX, but it's better to rephrase or ensure such constructs are in code blocks (using backticks `` `variable_name` ``) or math mode if appropriate. Prefer to avoid unescaped special characters in plain narrative text.
        *   Similarly, ensure backslashes `\` are not used in plain text in a way that LaTeX would interpret as a command.
    *   **Tables:** Use standard Pandoc-compatible Markdown for tables (e.g., pipes `|` and hyphens `-`).
    *   **Headings:** Use standard `#`, `##`, `###`, etc., for headings.
    *   **Lists:** Use standard Markdown for bulleted (`*`, `-`, `+`) and numbered lists.
    *   **Keep it Clean:** Prioritize clear, standard, and unambiguous Markdown. Avoid overly complex or non-standard Markdown structures that might confuse the LaTeX converter.

    **Output Requirements for Your Assigned Part:**
    *   Adhere strictly to the section numbers and titles provided for your part.
    *   Use Markdown for formatting (H1 for Part Title, H2 for Section Titles, H3/H4 for sub-sections).
    *   Ensure your output is a **CONTINUOUS BLOCK OF TEXT** representing only your assigned sections, ready to be concatenated with other parts. Do NOT include any preamble like "Here is Part X..."
    *   Be incredibly verbose, analytical, precise, and expansive. Each of your assigned sections should be a multi-page deep dive in ambition.
""")

synthesis_agent_part1_market_context = Agent(
    model=OpenAIChat(id="gpt-4o", timeout=400),
    instructions=_synthesis_agent_common_instructions + dedent("""\
        **YOUR ASSIGNED TASK: Generate Part I: Executive Overview & Comprehensive Market Context.**
        This part should be **7-10+ pages (approx. 15,000 - 25,000+ characters)**.
        You are responsible for producing the following sections with extreme depth and numerical integration:

        ### Part I: Executive Overview & Comprehensive Market Context

        #### 1. Title Page & Detailed Disclaimer 
        **(Generate a professional title for the ENTIRE report based on the primary subject. The disclaimer must be comprehensive, covering limitations, data sources, no investment advice, forward-looking statement risks, etc. Aim for 0.5 - 1 page for the disclaimer.)**

        #### 2. Hyper-Detailed Table of Contents
        **(Based on the full 27-section structure of the ENTIRE report, create a detailed multi-level table of contents. This will require you to list out all 27 section titles and their main sub-headings as defined in the master prompt for the full report structure.)**

        #### 3. Extended Executive Summary (Min. 2-3 pages, ~1000-1500 words for THIS SECTION ALONE)
        *   **In-Depth Investment Thesis:** (Articulate the core argument for the primary subject with supporting pillars in several detailed paragraphs, drawing from ALL sub-agent inputs to form this initial thesis.)
        *   **Granular Key Findings:** (Detail the most critical takeaways from EACH of the five sub-agent input categories: Financial Data, News, Research, ESG, Macro. Be specific with numbers and key insights.)
        *   **Definitive Recommendation & Rationale:** (Propose a Buy/Hold/Sell/Speculative Buy for the primary subject. Support this with a multi-paragraph, evidence-based justification, referencing key data points from all sub-agent inputs.)
        *   **Comprehensive Risk/Reward Profile:** (Elaborate significantly on 3-5 major upside catalysts and 3-5 major downside risks for the primary subject, discussing probability and potential impact using data from inputs.)
        *   **Valuation Conclusion Summary:** (Briefly state an overall valuation conclusion based on a quick synthesis of financial data – this will be expanded massively in Part IV later.)

        #### 4. Global Macroeconomic & Geopolitical Environment – In-Depth Review (Min. 2-3 pages for THIS SECTION ALONE - Massively elaborate on `macro_agent` input. For EACH sub-point below, provide multiple paragraphs of detailed analysis, quoting specific numbers, forecasts, and sources from the `macro_agent` input and explaining their direct and indirect impact on the primary subject of the report and its industry.)
        *   Detailed Analysis of Current Global Economic Climate: (Discuss key regions, growth drivers, and prevailing uncertainties with supporting data.)
        *   Monetary Policy Deep Dive: (Central bank actions (Fed, ECB, etc.), interest rate trajectory, quantitative easing/tightening, and profound implications for different asset classes and the target sector.)
        *   Inflationary Pressures: (Granular analysis of CPI/PPI components, core vs. headline, supply-side vs. demand-pull drivers, wage inflation, and impact on corporate profitability and consumer spending.)
        *   GDP Growth Dynamics: (Global, regional, and key national GDP forecasts, sectoral contributions, recession probabilities, and leading economic indicators.)
        *   Currency Market Volatility & International Trade: (Major currency pair analysis, impact of FX on multinational company earnings, trade tensions, protectionism, and supply chain regionalization.)
        *   Geopolitical Flashpoints & Strategic Implications: (Detailed discussion of specific ongoing geopolitical events, their potential escalation, and direct/indirect consequences for the industry and target company.)

        #### 5. Industry Deep Dive: Structure, Dynamics, and Long-Term Trajectory (Min. 3-4 pages for THIS SECTION ALONE - Massively elaborate on `news_agent`, `research_agent` inputs, and general industry context from `financial_data_agent`. For EACH sub-point below, provide multiple paragraphs of detailed analysis, quoting specific numbers, market sizes, growth rates, and sources from the inputs and explaining their relevance to the primary subject.)
        *   Exhaustive Industry Definition & Segmentation: (Detailed breakdown of industry structure, value chain, key sub-sectors, and their interdependencies.)
        *   Market Sizing & Growth Projections: (Historical market size, recent growth rates, and multi-year forecasts (e.g., 5-10 years) with data from reputable sources. Cite sources for all projections.)
        *   Fundamental Industry Drivers: (In-depth analysis of technological advancements, regulatory shifts, evolving consumer preferences, demographic trends, and economic factors propelling or hindering industry growth.)
        *   Disruptive Technologies & Innovation Ecosystem: (Detailed review of game-changing technologies, R&D trends, patent landscapes, and the role of startups vs. incumbents.)
        *   Comprehensive Porter's Five Forces Analysis: (Provide multiple detailed paragraphs for *each* force, supported by specific industry examples and data from inputs.)
        *   Industry Life Cycle & Maturity: (Assess the current stage and its implications for growth, competition, and profitability.)
        *   Key Success Factors & Competitive Imperatives for industry participants.
        *   Regulatory Environment Overview for the Industry: (General overview of key regulations, compliance burdens, and potential policy changes specific to this industry, drawing from `macro_agent` or `news_agent` if relevant.)
    """),
    markdown=True,
)

synthesis_agent_part2_company_forensics = Agent(
    model=OpenAIChat(id="gpt-4o", timeout=400),
    instructions=_synthesis_agent_common_instructions + dedent("""\
        **YOUR ASSIGNED TASK: Generate Part II: Company-Specific Forensic Analysis for the PRIMARY SUBJECT of the report.**
        This part should be **7-10+ pages (approx. 15,000 - 25,000+ characters)** for the single company.
        You are responsible for producing the following sections (6-11) with extreme depth and numerical integration, focusing SOLELY on the primary company identified in the main query.

        ### Part II: Company-Specific Forensic Analysis: [Primary Company Name from Query]

        #### 6. Company [Primary Company Name]: Business Model, Strategy, & Operations – Exhaustive Review (Min. 2-3 pages for THIS SECTION. For EACH sub-point below, provide multiple paragraphs of detailed analysis, quoting specific numbers, product details, segment revenues, and strategic statements from ALL relevant sub-agent inputs - financial_data_agent for company info, news_agent for recent strategies, research_agent for analyst views on strategy.)
        *   Detailed Corporate History, Founding Vision, Key Milestones, and Strategic Pivots.
        *   Mission, Vision, Explicit Long-Term Strategic Objectives, and observable Corporate Culture.
        *   Comprehensive Product/Service Portfolio Analysis: Features, benefits, target markets, pricing strategy, competitive differentiation for each major offering. Include revenue contribution by product/service if available from `financial_data_agent`.
        *   In-depth Business Segment Breakdown: For each segment - operational details, market position, growth strategy, profitability analysis (using segment data from `financial_data_agent` if provided), inter-segment synergies.
        *   Global Operational Footprint: Detailed map of key markets, manufacturing sites, distribution networks, and market penetration strategies with specific regional performance data (from company reports via `research_agent` or `news_agent`).
        *   Supply Chain & Logistics: Analysis of supply chain structure, key suppliers, potential vulnerabilities, and resilience initiatives (drawing from `macro_agent` or `news_agent` if relevant to the company).

        #### 7. Company [Primary Company Name]: Leadership, Governance, Culture & Ownership – Deep Dive (Min. 1.5-2 pages for THIS SECTION. For EACH sub-point, provide multiple paragraphs, integrating specific details from `esg_agent` for Governance, `financial_data_agent` for insider/institutional ownership if available, and `news_agent` for leadership changes or governance news.)
        *   Extensive Profiles of Key Management Team: CEO, CFO, COO, CTO, key divisional heads – background, tenure, expertise, past performance, strategic influence, compensation details if available.
        *   Board of Directors – Detailed Scrutiny: Composition (skills matrix, diversity metrics from `esg_agent`), independence (% independent directors), committee effectiveness (audit, compensation, nomination/governance – roles and key members), director qualifications and attendance.
        *   Forensic Corporate Governance Assessment: Shareholder rights (voting structure), transparency in reporting (quality of disclosures), code of ethics, anti-corruption measures, board oversight mechanisms, history of governance-related controversies (from `esg_agent` or `news_agent`).
        *   Major Shareholder Analysis: Breakdown of institutional vs. retail ownership, list of top 5-10 institutional holders with % ownership (from `financial_data_agent`), activist investor presence (from `news_agent` or `research_agent`), insider ownership and significant recent trading patterns.
        *   Executive Compensation Deep Dive: Detailed analysis of compensation structure (salary, bonus, equity components – from proxy statements if found by `research_agent` or `esg_agent`), alignment with short-term and long-term performance (financial and non-financial/ESG), peer benchmarking.
        *   Corporate Culture: Observable aspects, employee reviews (e.g., common themes from Glassdoor if mentioned by `news_agent` or `research_agent`), impact on innovation and execution.

        #### 8. Company [Primary Company Name]: Unpacking Financial Performance – Granular Review (Min. 3-4 pages for THIS SECTION. This section MUST be saturated with numbers. For EVERY financial item and ratio from `financial_data_agent`'s exhaustive output, provide its values for all reported periods (5-7 years, 8-12 quarters), calculate and state growth rates (YoY, QoQ), explain the trend in multiple paragraphs, compare to direct competitors if data allows, and interpret its meaning for the company's health and strategy.)
        *   **Revenue Analysis (5-7 Year Trend & Last 8-12 Quarters):** (Detailed breakdown by segment, geography, product line if in `financial_data_agent`. Analyze growth drivers (volume, price, mix), quality of revenue, customer concentration. Compare with peers.)
        *   **Profitability Analysis (5-7 Year Trend & Last 8-12 Quarters):**
            *   Gross Profit & Margin: (COGS analysis, input cost pressures, efficiency gains from `financial_data_agent`. Context from `news_agent` or `macro_agent`.)
            *   Operating Profit (EBIT) & Margin: (Detailed R&D, SG&A expense trends, operating leverage from `financial_data_agent`. Context from `news_agent`.)
            *   Net Profit & Margin: (Impact of interest, taxes, non-recurring items from `financial_data_agent`.)
            *   Trend analysis and comparison with 3-5 key competitors for all margins.
        *   **Expense Structure Deep Dive:** (Multi-year and multi-quarter trends in R&D (% of sales, absolute), SG&A (% of sales, absolute), and other major operating expenses from `financial_data_agent`. Efficiency ratio analysis.)
        *   **Balance Sheet Forensics (Last 5-7 Years & Last 8-12 Quarters):**
            *   Asset Quality & Composition: (Detailed review of all current vs. non-current assets from `financial_data_agent`.)
            *   Liquidity Position: (Current Ratio, Quick Ratio, Cash Ratio trends and peer comparison using `financial_data_agent` data.) Working capital cycle analysis.
            *   Capital Structure & Solvency: (Debt-to-Equity, Total Debt-to-Total Assets, Net Debt-to-EBITDA, Interest Coverage Ratio trends from `financial_data_agent`. Debt maturity profile. Credit ratings if available.)
        *   **Cash Flow Statement Deep Dive (Last 5-7 Years & Last 8-12 Quarters):**
            *   Quality of Operating Cash Flow (CFO): (Reconciliation from net income, key adjustments from `financial_data_agent`. CFO trends vs. Net Income.)
            *   Investing Cash Flow (CFI): (Capital expenditure trends, acquisitions, divestitures from `financial_data_agent`.)
            *   Financing Cash Flow (CFF): (Debt issuance/repayment, equity issuance/buybacks, dividend payments from `financial_data_agent`.)
            *   Free Cash Flow (FCF) Analysis: (Calculation shown using `financial_data_agent` numbers, trends, FCF margin, FCF conversion.)
        *   **Exhaustive Key Performance Indicators (KPIs) & Ratio Analysis:** (For ALL ratios provided by `financial_data_agent`, provide the value for each reported period, explain the trend in painful detail, compare to 2-3 direct competitors if data allows, and interpret what it means for the company. This part must be incredibly dense with numbers and analysis.)
        *   **Dividend Analysis (if applicable):** (Dividend per share, payout ratio, dividend yield trends, sustainability of dividends, using `financial_data_agent` data.)

        #### 9. Company [Primary Company Name]: Stock Dynamics & Multi-Indicator Technical Analysis (Min. 1.5-2 pages for THIS SECTION. Based on `financial_data_agent`'s technical data, for EACH indicator (SMA, EMA, RSI, MACD, Bollinger, Stochastic, Volume), explain its current reading, historical context, what the value implies (bullish/bearish/neutral, overbought/oversold), and how it fits into the broader technical picture. Discuss S&R levels and chart patterns if identified.)
        *   Long-Term & Short-Term Price Chart Analysis (Descriptive, based on data).
        *   Support & Resistance Levels (Specific levels from `financial_data_agent` data).
        *   Trendline Analysis (If data implies).
        *   Chart Pattern Recognition (If data implies).
        *   Moving Averages Deep Dive (Use all MAs from `financial_data_agent`).
        *   Oscillator Analysis (RSI, MACD, Stochastic from `financial_data_agent`).
        *   Bollinger Bands Analysis (Using data from `financial_data_agent`).
        *   Volume Analysis (Correlate reported volume with price movements).
        *   Volatility Assessment (Beta, Standard Deviation from `financial_data_agent`).

        #### 10. Company [Primary Company Name]: Strategic Impact of Recent News & Corporate Developments (Min. 1.5-2 pages for THIS SECTION. For EACH of the 10-15 news items from `news_agent`'s JSON output, provide an extensive multi-paragraph analysis. Quote the headline, date, source, and `ultra_detailed_summary`. Then, deeply analyze its strategic rationale, **quantify its financial/operational impact using the `quantitative_impact_data` and `direct_quotes` from the news input**, discuss market/stock reaction, and assess long-term implications for the company's strategy, financials, and competitive position. Connect news to ongoing themes.)

        #### 11. Company [Primary Company Name]: Synthesis of Analyst Opinions & Independent Research (Min. 1.5-2 pages for THIS SECTION. For EACH of the 3-5 analyst reports and 1-2 research pieces from `research_agent`'s JSON output, provide an exhaustive multi-paragraph summary and analysis. **Quote extensively from the `extensive_key_excerpts`, `investment_thesis_summary`, `key_catalysts_verbatim`, `key_risks_verbatim`, `financial_model_assumptions_verbatim`, and `valuation_methodology_verbatim` fields.** Discuss the analyst's core thesis, specific financial model assumptions, valuation methodology, price target derivation, and key catalysts/risks. Compare and contrast views. Critically evaluate assumptions.)
    """),
    markdown=True,
)

synthesis_agent_part3_strategic_assessment = Agent(
    model=OpenAIChat(id="gpt-4o", timeout=400),
    instructions=_synthesis_agent_common_instructions + dedent("""\
        **YOUR ASSIGNED TASK: Generate Part III: Holistic Strategic & Competitive Assessment.**
        This part should be **6-8+ pages (approx. 12,000 - 20,000+ characters)**.
        You are responsible for producing the following sections (12-15) with extreme depth and numerical integration, comparing the primary subject company with its competitors and analyzing its strategic assets.

        ### Part III: Holistic Strategic & Competitive Assessment

        #### 12. Deep Dive into Competitive Forces & Market Positioning (Min. 2-3 pages for THIS SECTION. Use `financial_data_agent` for competitor financial data if mentioned in primary company's peer list, `news_agent` for competitor news/strategies, and `research_agent` for analyst views on competitive landscape. For EACH sub-point, be exhaustive.)
        *   Identification and **exhaustive profiles of 3-5 key direct competitors AND 2-3 significant indirect/emerging competitors.** (For each competitor: approximate size, core strategy, key products, publicly known strengths and weaknesses. Use news/research inputs.)
        *   **Granular Comparative Financial Analysis:** Create detailed Markdown tables benchmarking the primary company against these key competitors across a wide range of financial ratios (Profitability, Liquidity, Solvency, Efficiency, Market Multiples – **use ALL relevant ratios for which `financial_data_agent` provided data for the primary company and attempt to find/cite data for competitors from `research_agent` or `news_agent` if available, or state if direct competitor data is not in inputs**). Write multiple paragraphs discussing reasons for variances for each ratio category.
        *   **Market Share Analysis:** Discuss historical and current market share for the primary company and key competitors in primary segments/geographies, using data from `research_agent` or `news_agent` if provided. Analyze trends and competitive dynamics.
        *   **Product Portfolio & Innovation Benchmarking:** Compare R&D spending (as % of revenue and absolute, from `financial_data_agent` for primary co., estimate for peers if possible from `research_agent`), patent activity (if mentioned in research), product development pipelines, and technological differentiation.
        *   **Brand Strength & Marketing Effectiveness:** Compare brand perception, customer loyalty (if data exists in inputs), and marketing strategies (from news/research).
        *   **Distribution Channels & Go-to-Market Strategies:** Comparative analysis based on available information.

        #### 13. Exhaustive SWOT Analysis (Min. 1.5-2 pages for the primary company. Be EXTREMELY specific and provide MULTIPLE (3-5) supporting examples/data points from ANY of the sub-agent inputs for EACH of the S, W, O, T elements.)
        *   **Strengths (Internal):** (Detail 5-7 distinct core competencies, competitive advantages, strong financial aspects (e.g., "Strong FCF generation of $X in YYYY" from `financial_data_agent`), valuable assets, unique capabilities. Quantify and cite input source for each point.)
        *   **Weaknesses (Internal):** (Detail 5-7 distinct internal limitations, areas for improvement, financial vulnerabilities (e.g., "High D/E ratio of Z" from `financial_data_agent`), operational inefficiencies. Quantify and cite input source.)
        *   **Opportunities (External):** (Detail 5-7 distinct market trends (e.g., "Market for X growing at Y% CAGR" from `research_agent`), unmet customer needs, technological advancements, potential new markets/segments, favorable regulatory changes the company can exploit. Quantify and cite input.)
        *   **Threats (External):** (Detail 5-7 distinct competitive pressures (e.g., "Competitor A launched new product Z" from `news_agent`), disruptive technologies, unfavorable regulatory changes (from `macro_agent`), macroeconomic headwinds, changing consumer preferences that pose a risk. Quantify and cite input.)

        #### 14. Innovation Trajectory, R&D Prowess, & Sustainable Competitive Advantages (Economic Moat) (Min. 2-3 pages for THIS SECTION. Integrate `financial_data_agent` for R&D spend, `news_agent` for product news, `research_agent` for tech insights.)
        *   **In-depth Assessment of R&D Strategy:** Analyze R&D spending levels (absolute USD and as % of revenue, trends over 5 years from `financial_data_agent`). Compare R&D spend with 2-3 key competitors. Discuss focus areas of R&D (from news/research) and linkage to corporate strategy.
        *   **Analysis of R&D Productivity & IP Strength:** Discuss patent portfolio details if available (number of patents, key areas, from research/news). Success rate of new product introductions (qualitative from news, or quantitative if data available). Time-to-market for new products.
        *   **Evaluation of Key Technological Capabilities:** Detail the company's core technologies and proprietary IP. How defensible is this IP? (Based on research/news).
        *   **Culture of Innovation:** Discuss evidence of an innovative culture (from news/research, employee reviews if cited) and ability to attract/retain top R&D talent.
        *   **Economic Moat Analysis (Be Detailed for Each Source of Moat):**
            *   Intangible Assets: Brand value (any rankings or valuations? from research?), patents (strength, breadth), regulatory licenses. Provide specific examples.
            *   Switching Costs: For customers to switch to competitors. Quantify if possible (e.g., cost, time, risk).
            *   Network Effects: Does the product/service become more valuable as more users join? Provide evidence.
            *   Cost Advantages: Sustainable cost advantages from scale, proprietary processes, unique assets, or supply chain. Quantify the advantage if possible (e.g., "X% lower production cost than peers").
            *   Efficient Scale: Do market dynamics limit the number of competitors that can operate profitably?
            *   **Sustainability of Moat:** How is the company defending and expanding its moat(s)? What are the key threats to its moat?

        #### 15. ESG Deep Dive: Integration, Performance, Risks & Opportunities (Min. 2-3 pages for THIS SECTION. This MUST be a forensic examination of the `esg_agent`'s highly detailed JSON input. For EVERY SINGLE data point, target, metric, rating, and policy mentioned in the `esg_agent` input, you must state it, explain its significance, analyze trends, compare to peers if data allows, and discuss its implications for risk, opportunity, and valuation. Be painfully detailed.)
        *   **Environmental Strategy & Performance:** (Exhaustively analyze all E data: climate strategy, GHG emissions Scope 1/2/3 with trends and intensities, energy consumption & renewables %, water usage, waste management & circularity metrics, biodiversity efforts, environmental CAPEX, fines. For each, quote the number from `esg_agent` and elaborate for multiple paragraphs.)
        *   **Social Responsibility & Human Capital:** (Exhaustively analyze all S data: employee metrics like turnover & D&I stats, labor practices & safety (LTIFR), community investment values, product responsibility details like recalls or data breaches, human rights policies. For each, quote the number/policy from `esg_agent` and elaborate for multiple paragraphs.)
        *   **Corporate Governance Excellence & Ethical Conduct:** (Exhaustively analyze all G data: board structure details like % independence & diversity, exec comp structure & ESG links, shareholder rights, ethics policies & fines. For each, quote the details from `esg_agent` and elaborate for multiple paragraphs.)
        *   **ESG Ratings & Benchmarking Detailed Analysis:** (Discuss EACH ESG rating (MSCI, Sustainalytics, CDP) provided by `esg_agent`. Explain the score, its trend, what it means, key positive/negative factors cited by the rating agency, and how the company compares to specific industry peer ratings if available.)
        *   **Financial Materiality of ESG Factors:** (Critically analyze how specific E, S, and G factors could translate into financial risks (e.g., carbon taxes, fines, reputational damage, stranded assets) or opportunities (e.g., green revenue streams, operational savings, attracting talent, enhanced brand value). Quantify where possible.)
    """),
    markdown=True,
)

synthesis_agent_part4_valuation_outlook = Agent(
    model=OpenAIChat(id="gpt-4o", timeout=400),
    instructions=_synthesis_agent_common_instructions + dedent("""\
        **YOUR ASSIGNED TASK: Generate Part IV: Advanced Valuation, Scenario Analysis, Risk Matrix, & Strategic Outlook.**
        This part should be **7-10+ pages (approx. 15,000 - 25,000+ characters)**.
        You are responsible for producing the following sections (16-20) with extreme depth and numerical integration, performing detailed valuation work based on inputs and providing a forward-looking view.

        ### Part IV: Advanced Valuation, Scenario Analysis, Risk Matrix, & Strategic Outlook

        #### 16. Rigorous Multi-Model Valuation & Intrinsic Value Assessment (Min. 3-4 pages for THIS SECTION. This is a CRITICAL section requiring deep numerical work. Use `financial_data_agent` for historicals and peer multiples. Use `research_agent` for analyst models/assumptions if any were extracted. If not, you must make and state reasonable assumptions for DCF, justifying each one with reference to historical data, industry trends, or macro outlook. SHOW YOUR WORK for DCF if building one up.)
        *   **Primary Valuation – Discounted Cash Flow (DCF) Analysis (MUST BE EXTREMELY DETAILED):**
            *   Explicit Projection Period (e.g., 5-10 years).
            *   **Detailed Assumptions (For EACH assumption, provide a multi-sentence justification referencing historical data from `financial_data_agent`, industry trends from `research_agent`/`news_agent`, or macro outlook from `macro_agent`):**
                *   Revenue Growth Rates (year-by-year for projection period).
                *   Operating Margins (or key expense ratios like COGS/SG&A/R&D as % of revenue, year-by-year).
                *   Effective Tax Rates.
                *   Capital Expenditures (as % of revenue or absolute).
            *   Calculation of Unlevered Free Cash Flow (UFCF) for each projection year (show the formula: EBIT(1-T) + D&A - Capex - ΔNWC).
            *   **Calculation of Weighted Average Cost of Capital (WACC) (Show ALL inputs and calculations):**
                *   Cost of Equity (Ke) using CAPM: Risk-Free Rate (current 10Y or 30Y Treasury yield - state which), Equity Risk Premium (state assumed value, e.g., 4-6%), Beta (from `financial_data_agent`).
                *   Cost of Debt (Kd): Company's average interest rate on debt (estimate from interest expense / total debt if not directly available from `financial_data_agent`) OR yield on its publicly traded bonds. State pre-tax and after-tax Kd.
                *   Market Value of Equity (E) (Market Cap from `financial_data_agent`).
                *   Market Value of Debt (D) (Estimate if book value is used, or use market value if available).
                *   WACC Formula: WACC = (E/(D+E))*Ke + (D/(D+E))*Kd*(1-Tax Rate).
            *   **Terminal Value Calculation (Choose ONE method and justify; show calculation):**
                *   Gordon Growth Model (Perpetuity Growth Method): TV = UFCF_final_year * (1+g) / (WACC-g). Justify the perpetual growth rate (g) (e.g., long-term inflation or GDP growth rate).
                *   OR Exit Multiple Method: TV = EBITDA_final_year * Exit Multiple. Justify the chosen Exit Multiple (e.g., based on peer LTM EV/EBITDA multiples from `financial_data_agent` or `research_agent`).
            *   Calculation of Enterprise Value (PV of UFCFs + PV of TV) and Intrinsic Equity Value (EV - Net Debt + Cash). Derive intrinsic value per share.
            *   **Sensitivity Analysis (Present as Markdown Tables):** Show how intrinsic value per share changes with +/- 1-2% variations in WACC and +/- 0.5-1% variations in perpetual growth rate (if GGM used) OR +/- 1-2x variations in Exit Multiple.
            *   **Scenario Analysis (Base Case, Bull Case, Bear Case DCF):** Clearly state the different key assumptions (e.g., revenue growth, margins) for each scenario, linking them to specific optimistic/pessimistic views from `research_agent` or potential outcomes of risks/catalysts. Calculate and present the resulting valuation for each scenario.
        *   **Secondary Valuation – Public Market Comparables (Comps) Analysis (MUST BE DETAILED):**
            *   Selection of 5-7 truly comparable public companies (justify each comp based on business model, size, geography, risk profile). Use peer list from `financial_data_agent` if provided, or identify from `research_agent`.
            *   Gather and present in a Markdown table current LTM AND NTM (if available from `research_agent` or consensus estimates via `financial_data_agent`) multiples for all comps: P/E, P/S, P/B, EV/Sales, EV/EBITDA, EV/EBIT, PEG Ratio.
            *   Calculate and present mean, median, 25th percentile, 75th percentile multiples for the peer group for each key metric.
            *   Apply these peer group multiple ranges (median and 25th-75th) to the target company's corresponding LTM financial metrics (from `financial_data_agent`) to derive an implied valuation range per share for each multiple. Discuss which multiples are most relevant and why.
        *   **Secondary Valuation – Precedent Transaction Analysis (if relevant and data is available from `news_agent` or `research_agent`):**
            *   Identify 3-5 relevant M&A transactions in the industry over the past 2-3 years.
            *   For each transaction: Announce Date, Target, Acquirer, Deal Value (Equity & Enterprise), Key Transaction Multiples (e.g., EV/LTM Sales, EV/LTM EBITDA).
            *   Calculate and present mean, median, 25th, 75th percentile multiples for precedent transactions.
            *   Apply relevant transaction multiple ranges to the target company's metrics.
        *   **(Optional but good for depth) Sum-of-the-Parts (SOTP) Valuation:** If the company has distinct, separately reportable business segments (data from `financial_data_agent` or company reports via `research_agent`), attempt to value each segment individually using appropriate Comps or other methods and sum them up. Adjust for corporate overhead and net debt.
        *   **Valuation Summary & "Football Field" Chart (Describe what this would look like):** Consolidate the valuation ranges per share from ALL methods (DCF Base/Bull/Bear, Comps P/E, Comps EV/EBITDA, etc.) into a summary table. Describe how these would be visualized on a "football field" chart to show the confluence (or divergence) of valuation ranges. Discuss the strengths and weaknesses of each valuation method in the context of this specific company and industry. Arrive at a final concluded intrinsic value range.

        #### 17. Comprehensive Risk Factor Analysis & Mitigation Deep Dive (Min. 2-3 pages for THIS SECTION. For EACH of the 10-15 key risks you identify by synthesizing ALL sub-agent inputs (financial, news, research, ESG, macro), provide multiple paragraphs of analysis.)
        *   Systematic Identification of 10-15 Key Risks: Categorize (Market, Industry, Company-Specific Operational, Financial, Technological, Regulatory/Compliance, ESG, Geopolitical). **Draw specific risks from ALL sub-agent inputs (e.g., high beta from `financial_data_agent`, negative news from `news_agent`, analyst concerns from `research_agent`, ESG controversies from `esg_agent`, policy changes from `macro_agent`).**
        *   For EACH identified risk:
            *   **Detailed Description:** What is the risk? What are its specific drivers and potential triggers?
            *   **Likelihood Assessment:** (Qualitative: Low, Medium, High) with justification.
            *   **Potential Financial & Strategic Impact:** (Qualitative: Low, Medium, High, or try to quantify if possible, e.g., "a 10% fall in demand due to X could reduce revenue by $Y million"). How would it affect key financials (revenue, profit, cash flow) or strategic goals?
            *   **Company's Mitigation Strategies:** What is the company currently doing to manage or mitigate this risk (from company reports via `research_agent`, `news_agent`, or `esg_agent`)? How effective are these strategies?
            *   **Residual Vulnerability:** What is the remaining exposure despite mitigation efforts? Are there unmitigated aspects?
        *   **Risk Matrix (Describe or create a Markdown table):** Summarize key risks, likelihood, impact, and mitigation effectiveness.
        *   **Stress Testing / Scenario Impact (Qualitative):** Discuss how the company might fare under a severe but plausible adverse scenario (e.g., deep recession, major regulatory crackdown, critical supply chain failure).

        #### 18. Growth Strategy Analysis & Long-Term Catalysts – Exhaustive Review (Min. 2-3 pages for THIS SECTION. Use `news_agent` for recent strategic announcements, `research_agent` for analyst views on strategy and market opportunities, `financial_data_agent` for R&D spend and capex as indicators of investment in growth.)
        *   **Detailed Articulation of Stated Organic Growth Strategy:** Based on company statements (from news/research), analyze their approach to: market penetration (gaining share in existing markets), market development (entering new geographic or demographic markets), product development (new products for existing markets), and diversification (new products in new markets). Provide specific examples for each.
        *   **Analysis of Key Secular Growth Drivers:** Identify 3-5 major long-term trends (e.g., AI adoption, EV transition, aging population, digitalization – from `macro_agent` or `research_agent`) and analyze in detail how the company's strategy and products are positioned to capitalize on them. Provide market size and growth forecasts for these trend-driven opportunities.
        *   **Evaluation of Inorganic Growth Strategy (M&A):** Review the company's M&A history (if any, from `news_agent`). What is their stated M&A criteria? Are they acquisitive? Potential for future strategic acquisitions, partnerships, or joint ventures that could accelerate growth (based on `research_agent` speculation or company hints). Assess integration capabilities and risks.
        *   **Assessment of Execution Capability:** Evaluate the company's ability to execute its stated growth plans, considering its financial resources (from `financial_data_agent`), technological capabilities (from `research_agent`), management track record, and the competitive environment.
        *   **Identification of 5-7 Major Long-Term Catalysts:** For each catalyst (e.g., launch of a breakthrough product, entry into a large new market, significant regulatory win, successful large-scale M&A), explain it in detail, estimate its potential timeline, and analyze its potential impact on revenue, earnings, and valuation.

        #### 19. Short-Term Outlook (Next 12-24 Months) – Key Milestones & Expectations (Min. 1-1.5 pages for THIS SECTION. Use `financial_data_agent` for analyst estimates, `news_agent` for upcoming events/guidance.)
        *   **Company's Financial Guidance (if available from `news_agent` or investor relations section of research):** Detail any explicit guidance for upcoming quarters/year on revenue, EPS, margins, or key operational metrics. Compare this guidance with current analyst consensus estimates (from `financial_data_agent`).
        *   **Analyst Consensus Estimates & Revisions:** Discuss current consensus estimates for revenue and EPS for the next 4-8 quarters and next 2 fiscal years (from `financial_data_agent`). Have estimates been trending up or down? Why? (cite `news_agent` or `research_agent`).
        *   **Anticipated Key Events & Milestones:** List specific upcoming product launches, R&D readouts, earnings release dates, investor days, significant contract renewals, or regulatory decisions expected in the next 12-24 months (from `news_agent` or company calendar if accessible via research).
        *   **Potential Near-Term Catalysts & Headwinds:** Based on the above, identify 3-4 factors that could positively surprise (catalysts) and 3-4 factors that could negatively impact (headwinds) the company's performance and stock price in the short term.
        *   **Key Operational Metrics to Monitor:** What are the 3-5 most important non-financial KPIs that investors should track closely over the next 1-2 years to gauge execution (e.g., user growth, production units, contract wins)?

        #### 20. Long-Term Strategic Vision & Transformative Potential (3-5+ Years) (Min. 1-1.5 pages for THIS SECTION. Based on `research_agent`, `news_agent` for CEO statements, company vision statements.)
        *   **Analysis of Company's Stated Long-Term Vision:** What does the company aspire to be in 5-10 years? What major strategic ambitions has it articulated (e.g., to dominate a new market, to solve a major global problem, to achieve a certain scale)?
        *   **Assessment of Capability to Achieve Vision:** Critically evaluate the feasibility of this long-term vision given the company's current resources, competitive advantages (moat), innovation pipeline, and the evolving industry landscape. What are the biggest hurdles?
        *   **Potential for Industry Transformation:** Does the company have the potential to fundamentally reshape its industry or create new ones? What is its disruptive potential?
        *   **"Blue Sky" Scenarios / Optionality:** Are there any high-risk/high-reward long-term opportunities or "moonshots" the company is pursuing that are not fully reflected in current valuations but could offer significant future upside?
        *   **Long-Term Value Creation Narrative:** Synthesize how the company aims to create sustainable shareholder value over the very long term.
    """),
    markdown=True,
)

synthesis_agent_part5_thesis_recommendations = Agent(
    model=OpenAIChat(id="gpt-4o", timeout=400),
    instructions=_synthesis_agent_common_instructions + dedent("""\
        **YOUR ASSIGNED TASK: Generate Part V: Definitive Investment Thesis & Actionable Strategic Recommendations.**
        This part should be **5-7+ pages (approx. 10,000 - 18,000+ characters)**.
        You are responsible for producing the following sections (21-24) with extreme depth and numerical integration, drawing firm conclusions from all prior analysis.

        ### Part V: Definitive Investment Thesis & Actionable Strategic Recommendations

        #### 21. Consolidated & Deeply Elaborated Investment Thesis (Min. 2-3 pages for THIS SECTION. This is the culmination of all prior analysis. Synthesize findings from ALL previous parts (Market, Company, Competition, ESG, Valuation, Risks, Growth) to construct a powerful, multi-faceted investment thesis.)
        *   **Reiteration and Profound Elaboration of Central Argument:** Clearly state your core investment thesis (e.g., "We recommend a BUY rating on Company X due to its dominant market position in a secularly growing industry, strong financial performance, sustainable competitive advantages, and an attractive valuation relative to its growth prospects, despite identifiable risks in A, B, and C.").
        *   **Supporting Pillar 1 (e.g., Market Leadership & Growth):** Provide several paragraphs detailing evidence from Parts I & III that support this pillar. Quote specific market share data, growth rates, industry driver analysis.
        *   **Supporting Pillar 2 (e.g., Financial Strength & Profitability):** Provide several paragraphs detailing evidence from Part II (Section 8) that support this. Quote specific financial ratios, margin trends, FCF generation.
        *   **Supporting Pillar 3 (e.g., Competitive Moat & Innovation):** Provide several paragraphs detailing evidence from Part III (Section 14) that support this. Discuss specific moat sources and R&D successes.
        *   **(Optional) Supporting Pillar 4 (e.g., ESG Leadership or Turnaround Story, etc.).**
        *   **Key Assumptions & Variables Underpinning Thesis:** Explicitly list 5-7 critical assumptions your thesis relies on (e.g., "Assumes continued X% market growth," "Assumes successful launch of Product Y," "Assumes margins remain above Z%"). Discuss the sensitivity of your thesis to these assumptions.
        *   **Alignment with Investor Profiles:** Discuss in detail how this investment thesis aligns (or misaligns) with different investor types (e.g., growth, value, GARP, income, ESG-focused) and their respective risk tolerances.
        *   **Addressing Counterarguments/Bearish Views:** Proactively identify 2-3 main bearish arguments against the company (from `research_agent` if available, or based on identified risks). Provide well-reasoned rebuttals or acknowledge their validity and how they are factored into your overall thesis.
        *   **Linchpin Factors:** What 2-3 factors are absolutely critical for the thesis to play out successfully?

        #### 22. Price Target Rationale & Expected Return Profile (Min. 1-1.5 pages for THIS SECTION. Be very specific with numbers from Part IV, Section 16.)
        *   **Derivation of 12-Month Price Target:** Clearly explain how your recommended 12-month (or other appropriate timeframe) price target is derived. Explicitly state which valuation methodology (or blend of methodologies) from Part IV, Section 16, forms the primary basis for your target (e.g., "Our $150 PT is based 60% on our DCF base case valuation of $155 and 40% on the median P/E multiple from our peer comparables analysis, which implied $142."). Show the weighting if a blend is used.
        *   **Calculation of Expected Upside/Downside:** From the current stock price (quoted from `financial_data_agent`), calculate the percentage upside to your price target or downside if it's lower.
        *   **Expected Total Shareholder Return (TSR):** Calculate expected TSR by adding the expected capital appreciation (%) and the forward dividend yield (%, from `financial_data_agent`).
        *   **Price Target Ranges (Bull, Base, Bear Scenarios):** Reiterate the price targets derived from your Bull, Base, and Bear case valuation scenarios in Part IV, Section 16. Explain the key differentiating assumptions that drive these different target outcomes.
        *   **Key Events/Data for Re-rating:** What specific future events, data releases, or milestone achievements (or failures) could cause you to revise your price target up or down? Link to catalysts/risks.

        #### 23. Actionable Strategic Considerations for Different Investor Types (Min. 1 page for THIS SECTION. Provide concrete, actionable advice.)
        *   **For Long-Term Growth Investors:** Discuss optimal entry point considerations (e.g., "Consider accumulating on dips below $X, representing Y multiple"), position sizing within a diversified portfolio, and key long-term strategic milestones to monitor that would validate/invalidate the long-term thesis.
        *   **For Value Investors:** Is there a margin of safety at current prices relative to your intrinsic value estimate? What conditions would make it a compelling value play?
        *   **For Tactical / Shorter-Term Traders (if applicable, otherwise focus on long-term):** Identify key technical levels (support/resistance from Part II, Section 9) to watch for entry/exit. Discuss potential near-term catalysts (from Part IV, Section 19) that could drive short-term price movements. Suggest risk management techniques (e.g., stop-loss levels based on technicals).
        *   **For Income Investors (if company pays a dividend):** Analyze dividend sustainability, dividend growth prospects (based on FCF and payout ratio from Part II, Section 8), and attractiveness of the current yield relative to alternatives and risk.
        *   **Portfolio Construction Context:** How might this stock fit into different types of diversified portfolios (e.g., high growth, balanced, defensive)? What is its correlation with broader market indices (Beta from Part II, Section 9)?

        #### 24. Final Concluding Remarks & Comprehensive Outlook Synthesis (Min. 1.5-2 pages for THIS SECTION. This is your grand finale, a powerful summary of your exhaustive work.)
        *   **Masterful Wrap-up:** Elegantly synthesize the entire, multi-faceted analysis from all preceding parts of the report.
        *   **Reiteration of Core Investment Message:** Clearly and forcefully restate your primary investment conclusion and the definitive rationale behind it.
        *   **Balanced Perspective - Opportunities vs. Challenges:** Provide a final, nuanced summary of the most compelling opportunities that could drive significant value, juxtaposed against the most critical challenges and risks the company must navigate.
        *   **Long-Term Vision for the Company:** Offer a final thought on the company's ultimate potential and its role in shaping the future of its industry over the next decade.
        *   **Concluding Investment Stance:** End with a clear, confident reiteration of your investment rating and overall perspective.
    """),
    markdown=True,
)

synthesis_agent_part6_appendices = Agent(
    model=OpenAIChat(id="gpt-4o", timeout=300),
    instructions=_synthesis_agent_common_instructions + dedent("""\
        **YOUR ASSIGNED TASK: Generate Part VI: Essential Appendices.**
        This part should be **3-5+ pages (approx. 6,000 - 12,000+ characters)**, primarily focused on presenting detailed data and standard information.
        You are responsible for producing the following sections (25-27) with clarity and accuracy, formatting data from sub-agent inputs into clean Markdown tables where appropriate.

        ### Part VI: Essential Appendices

        #### 25. Appendix A: Detailed Financial Statement Summaries
        **(This section requires you to take the DETAILED financial statement line items for the Income Statement, Balance Sheet, and Cash Flow Statement, for the last 5 fiscal years AND the last 4-8 quarters, as provided in the `financial_data_agent`'s JSON input, and format them into clean, readable Markdown tables. Ensure all figures are clearly labeled with periods (e.g., FY2022, Q3-2023) and units (e.g., USD millions). If growth rates were provided by `financial_data_agent`, include them as separate columns or notes.)**
        *   **Income Statements (5 Years Annual, 4-8 Quarters)**
            *   (Table for Annual Data)
            *   (Table for Quarterly Data)
        *   **Balance Sheets (5 Years Annual, 4-8 Quarters)**
            *   (Table for Annual Data)
            *   (Table for Quarterly Data)
        *   **Cash Flow Statements (5 Years Annual, 4-8 Quarters)**
            *   (Table for Annual Data)
            *   (Table for Quarterly Data)

        #### 26. Appendix B: Comprehensive Glossary of Key Financial, Technical, & Industry Terms Used
        **(Compile a glossary of at least 20-30 key financial, technical, and industry-specific terms that would have been used throughout a detailed report of this nature. Provide clear, concise definitions for each term. Examples: EPS, P/E Ratio, WACC, DCF, RSI, MACD, Scope 3 Emissions, SaaS, ARR, Proof-of-Stake, etc. Select terms relevant to the likely content of the full report.)**
        *   Term 1: Definition
        *   Term 2: Definition
        *   ... (list 20-30 terms)

        #### 27. Appendix C: Bibliography & Key Information Sources
        **(List the categories of information sources that were used by the sub-agents to compile their data. Do not make up specific URLs unless they were explicitly in the sub-agent's JSON output. Instead, list types of sources and the tools used.)**
        *   **Primary Data Sources:**
            *   Public Company SEC Filings (e.g., 10-K, 10-Q, 8-K, Proxy Statements) - (Implicitly used by YFinance and potentially research tools)
            *   Company Investor Relations Websites & Presentations - (Implicitly used by YFinance and potentially research/news tools)
            *   Company Sustainability Reports / ESG Disclosures - (Source for `esg_agent`)
        *   **Financial Data Platforms & APIs:**
            *   Yahoo Finance API (via `YFinanceTools`) - (Used by `financial_data_agent`)
        *   **News Aggregation & Search:**
            *   Google Search API (via `GoogleSearchTools`) - (Used by `news_agent`, `esg_agent`, `macro_agent`)
            *   Major Financial News Outlets (e.g., Reuters, Bloomberg, Wall Street Journal, Financial Times - as potentially surfaced by Google Search)
        *   **Specialized Research & Analysis Platforms:**
            *   Exa AI Search API (via `ExaTools`) - (Used by `research_agent` for analyst reports, white papers)
            *   Investment Bank Research Portals (if Exa surfaced reports from specific banks)
            *   Third-Party ESG Rating Agencies (e.g., MSCI, Sustainalytics, CDP - as potentially surfaced by `esg_agent` via Google Search)
        *   **Macroeconomic Data Sources:**
            *   International Monetary Fund (IMF) World Economic Outlook
            *   World Bank Global Economic Prospects
            *   Central Bank Publications (e.g., Federal Reserve, ECB)
            *   National Statistics Offices (e.g., Bureau of Labor Statistics, Eurostat)
            *   (These would be implicitly used by `macro_agent` when forming its analysis from Google Search results)
        *   **General Disclaimer:** "The specific articles, reports, and data points were dynamically sourced by AI agents at the time of report generation using the tools and platform categories listed above. Specific URLs for all news items are included in the `news_agent` data input."
    """),
    markdown=True,
)


async def generate_comprehensive_report_sequential(query_subject):
    logger.info(f"Starting ULTRA-COMPREHENSIVE report generation for: {query_subject}")
    
    # Initialize content variables with clear error messages
    data_payload = {
        "financial": "Financial Data Agent: No data retrieved or error in retrieval.",
        "news": "News Agent: No data retrieved or error in retrieval.",
        "research": "Research Agent: No data retrieved or error in retrieval.",
        "esg": "ESG Agent: No data retrieved or error in retrieval.",
        "macro": "Macroeconomic Agent: No data retrieved or error in retrieval."
    }
    
    # Define specific sub-queries
    financial_query = f"Provide ultra-detailed quantitative financial, technical, and analyst estimate data for {query_subject} as per exhaustive instructions."
    news_query = f"Gather most impactful and data-rich news (corporate, market, regulatory, competitive, industry) for {query_subject} over the last 4-6 weeks, detailing all numbers and quotes."
    research_query_exa = f"Find and extract extensive verbatim text from 3-5 full analyst reports, 1-2 in-depth industry/thematic research pieces, and 1-2 academic/white papers relevant to {query_subject} and its core technologies/markets."
    esg_query_google = f"Collect exhaustive, quantifiable ESG data (Environmental, Social, Governance) for {query_subject}, including specific metrics, targets, performance data, and ratings from sustainability reports and third-party providers."
    macro_query_google = f"Provide an extremely detailed, data-driven analysis of all key macroeconomic and geopolitical factors (inflation, interest rates, GDP, labor, regulations, geopolitics, supply chain, commodities, secular trends) specifically impacting {query_subject} and its industry, with quantifiable impacts."

    # Data Gathering Phase
    agent_tasks = {
        "financial": (financial_data_agent, financial_query, financial_data_agent.arun),
        "news": (news_agent, news_query, rate_limited_google_search),
        "research": (research_agent, research_query_exa, rate_limited_exa_search),
        "esg": (esg_agent, esg_query_google, rate_limited_google_search),
        "macro": (macro_agent, macro_query_google, rate_limited_google_search)
    }

    for key, (agent_instance, specific_query, method_to_call) in agent_tasks.items():
        try:
            logger.info(f"Collecting {key} data for: {query_subject} using query: \"{specific_query[:100]}...\"")
            # Await the method call correctly
            if method_to_call == agent_instance.arun: # Direct call for non-rate-limited
                 result = await agent_instance.arun(specific_query)
            else: # Call through rate-limited wrapper
                 result = await method_to_call(agent_instance, specific_query)

            data_payload[key] = result.content if hasattr(result, 'content') else str(result)
            logger.info(f"{key.capitalize()} data collected (approx. length: {len(data_payload[key])} chars)")
        except Exception as e:
            logger.error(f"Error collecting {key} data for {query_subject}: {str(e)}", exc_info=True)
            data_payload[key] = f"Error retrieving {key} data for {query_subject}: {str(e)}"

    logger.info("All data collection attempts complete. Beginning modular synthesis of ultra-comprehensive report...")
    
    # Prepare the full data payload string for each synthesis agent
    # (They are instructed to only use what's relevant to their part)
    full_synthesis_input_data_block = f"""
    **PRIMARY SUBJECT OF THIS ULTRA-COMPREHENSIVE INSTITUTIONAL REPORT:** {query_subject}

    **Section 1: Quantitative Financial Data & Technical Analysis Input (from financial_data_agent):**
    ```json
    {data_payload['financial']}
    ```

    **Section 2: News Intelligence & Recent Developments Input (from news_agent):**
    ```json
    {data_payload['news']}
    ```

    **Section 3: Deep Research, Analyst Opinions & Thematic Insights Input (from research_agent):**
    ```json
    {data_payload['research']}
    ```

    **Section 4: ESG (Environmental, Social, Governance) Factors & Sustainability Input (from esg_agent):**
    ```json
    {data_payload['esg']}
    ```

    **Section 5: Global Macroeconomic & Geopolitical Context Input (from macro_agent):**
    ```json
    {data_payload['macro']}
    ```
    **Instruction for ALL Synthesis Agents:** Based EXCLUSIVELY on the RELEVANT SECTIONS of the JSON inputs provided above AND your specific PART's comprehensive instructions (regarding section numbers, extreme elaboration, numerical integration, and target length for your part), generate your assigned portion of the ultra-comprehensive institutional-grade investment research report. Adhere strictly to the detailed multi-page structure and content requirements outlined in your primary instructions. Ensure every section within your assigned part is a deep dive and expands significantly on the provided data.
    """

    report_parts = []
    synthesis_agents_and_parts = [
        ("Part1_MarketContext", synthesis_agent_part1_market_context),
        ("Part2_CompanyForensics", synthesis_agent_part2_company_forensics),
        ("Part3_StrategicAssessment", synthesis_agent_part3_strategic_assessment),
        ("Part4_ValuationOutlook", synthesis_agent_part4_valuation_outlook),
        ("Part5_ThesisRecommendations", synthesis_agent_part5_thesis_recommendations),
        ("Part6_Appendices", synthesis_agent_part6_appendices),
    ]

    for part_name, agent_instance in synthesis_agents_and_parts:
        try:
            logger.info(f"Synthesizing {part_name} with input approx. {len(full_synthesis_input_data_block)} chars long. This will take time...")
            # Each agent gets the full data block but its instructions tell it which part to focus on
            part_result = await agent_instance.arun(full_synthesis_input_data_block) 
            part_content = part_result.content if hasattr(part_result, 'content') else str(part_result)
            report_parts.append(part_content)
            logger.info(f"{part_name} synthesis complete (approx. length: {len(part_content)} chars)")
            # Small delay between major synthesis steps
            await asyncio.sleep(random.uniform(1,3)) 
        except Exception as e:
            logger.error(f"Critical error during synthesis of {part_name}: {str(e)}", exc_info=True)
            report_parts.append(f"\n\n### ERROR GENERATING {part_name.upper()}\n\nError: {str(e)}\n\n")
            # Log the first 5000 chars of synthesis_input for debugging context window or content issues.
            logger.debug(f"Synthesis input for {part_name} (first 5k chars): {full_synthesis_input_data_block[:5000]}")

    final_report = "\n\n---\n\n".join(report_parts) # Join parts with a separator
    logger.info(f"ULTRA-COMPREHENSIVE report final assembly complete (total approx. length: {len(final_report)} chars)")
    
    # Post-generation length check
    if len(final_report) < 50000: # Adjusted threshold for "too short" given modularity
        logger.warning(f"Generated report is shorter ({len(final_report)} chars) than the target of 60k-100k+. Review sub-agent outputs and ALL synthesis agent instructions if more length is critical.")
    
    return final_report

def _convert_md_to_pdf(md_filepath, pdf_filepath):
    """Converts a markdown file to PDF using pandoc."""
    try:
        logger.info(f"Attempting to convert {md_filepath} to {pdf_filepath} using pandoc...")
        
        env = os.environ.copy()
        tex_bin_path = "/Library/TeX/texbin"
        if tex_bin_path not in env.get('PATH', ''):
            env['PATH'] = f"{tex_bin_path}:{env.get('PATH', '')}"
            logger.info(f"Temporarily prepended {tex_bin_path} to PATH for pandoc subprocess.")

        process = subprocess.run(
            ['pandoc', '--standalone', md_filepath, '-o', pdf_filepath], # Added --standalone
            check=True,
            capture_output=True,
            text=True,
            env=env 
        )
        logger.info(f"Successfully converted {md_filepath} to {pdf_filepath}.")
        logger.debug(f"Pandoc output: {process.stdout}")
        return True
    except FileNotFoundError:
        logger.error("Pandoc not found. Please ensure pandoc is installed and in your system's PATH.")
        print("ERROR: Pandoc not found. Please install pandoc to generate PDF reports.")
        return False
    except subprocess.CalledProcessError as e:
        logger.error(f"Pandoc conversion failed for {md_filepath}: {e}")
        logger.error(f"Pandoc stderr: {e.stderr}")
        print(f"ERROR: Pandoc conversion failed for {md_filepath}. Check logs for details.")
        return False
    except Exception as e:
        logger.error(f"An unexpected error occurred during PDF conversion: {e}", exc_info=True)
        print(f"ERROR: An unexpected error occurred during PDF conversion. Check logs for details.")
        return False

def _get_content_type(filepath):
    """Determines the content type based on file extension."""
    if filepath.endswith(".md"):
        return "text/markdown"
    elif filepath.endswith(".pdf"):
        return "application/pdf"
    else:
        return "application/octet-stream" # Default binary type

def _upload_to_do_spaces(local_filepath, object_name_override=None):
    """Uploads a file to DigitalOcean Spaces and returns its public URL."""
    do_key = os.getenv("DO_SPACES_KEY")
    do_secret = os.getenv("DO_SPACES_SECRET")
    do_bucket = os.getenv("DO_SPACES_BUCKET")
    do_region = os.getenv("DO_SPACES_REGION")

    if not all([do_key, do_secret, do_bucket, do_region]):
        logger.error("DigitalOcean Spaces credentials not fully configured in environment variables.")
        print("ERROR: DigitalOcean Spaces credentials (DO_SPACES_KEY, DO_SPACES_SECRET, DO_SPACES_BUCKET, DO_SPACES_REGION) are missing.")
        return None

    object_name = object_name_override if object_name_override else os.path.basename(local_filepath)
    content_type = _get_content_type(local_filepath)
    
    s3_client = boto3.client(
        's3',
        region_name=do_region,
        endpoint_url=f'https://{do_region}.digitaloceanspaces.com',
        aws_access_key_id=do_key,
        aws_secret_access_key=do_secret
    )

    try:
        logger.info(f"Uploading {local_filepath} to DigitalOcean Spaces bucket {do_bucket} as {object_name} with ContentType {content_type}...")
        with open(local_filepath, "rb") as f:
            s3_client.upload_fileobj(
                f,
                do_bucket,
                object_name,
                ExtraArgs={
                    'ACL': 'public-read',
                    'ContentType': content_type
                }
            )
        
        download_url = f'https://{do_bucket}.{do_region}.digitaloceanspaces.com/{object_name}'
        logger.info(f"Successfully uploaded {local_filepath} to {download_url}")
        return download_url
    except FileNotFoundError:
        logger.error(f"Local file not found for upload: {local_filepath}")
        print(f"ERROR: Local file not found for upload: {local_filepath}")
        return None
    except NoCredentialsError:
        logger.error("Boto3 credentials not available for DigitalOcean Spaces upload.")
        print("ERROR: Boto3 credentials not available for DigitalOcean Spaces upload.")
        return None
    except ClientError as e:
        logger.error(f"Boto3 client error during upload to DigitalOcean Spaces: {e}", exc_info=True)
        print(f"ERROR: Client error during upload to DigitalOcean Spaces: {e}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred during upload to DigitalOcean Spaces: {e}", exc_info=True)
        print(f"ERROR: An unexpected error occurred during upload to DigitalOcean Spaces: {e}")
        return None

def run_comprehensive_report(query_subject):
    main_orchestrator_query = f"Generate an ultra-comprehensive institutional-grade investment research report on {query_subject}, covering all aspects of its business, financials, market position, and future outlook in extreme detail, leveraging all specialized sub-agent data."

    print(f"Starting ULTRA-COMPREHENSIVE analysis for: {query_subject}")
    print("This process will take an EXTREMELY considerable amount of time (potentially 30-60+ minutes or even longer) due to extensive data gathering, meticulous rate limit management, and multiple complex, lengthy synthesis steps by the LLM.")
    print("Progress will be logged. Please be extremely patient and do not interrupt unless necessary.")
    
    report = "" # Initialize report string
    md_filename = "" # Initialize markdown filename
    pdf_filename = "" # Initialize pdf filename

    try:
        report_content = asyncio.run(generate_comprehensive_report_sequential(query_subject)) 
        
        print("\n\n=== RAW MARKDOWN REPORT (ULTRA-COMPREHENSIVE) ===\n\n")
        report_summary_display_length = 5000 
        report_summary = report_content[:report_summary_display_length] + f"\n\n... (report truncated after {report_summary_display_length} chars for terminal display) ..." if len(report_content) > report_summary_display_length else report_content
        print(report_summary)
        print(f"\nFull report length: {len(report_content)} characters.")
        print("\n\n=== END OF REPORT SUMMARY ===\n\n")
        
        timestamp = int(time.time())
        safe_query_part = "".join(c if c.isalnum() else "_" for c in query_subject[:40]).strip("_").replace("__","_")
        md_filename = f"FINANCE_REPORT_{safe_query_part}_{timestamp}.md"
        pdf_filename = f"FINANCE_REPORT_{safe_query_part}_{timestamp}.pdf"
        
        try:
            with open(md_filename, "w", encoding='utf-8') as f:
                f.write(report_content)
            print(f"Full Markdown report saved locally to: {md_filename}")
            
            # Convert to PDF
            pdf_conversion_success = _convert_md_to_pdf(md_filename, pdf_filename)
            if pdf_conversion_success:
                print(f"PDF report generated successfully: {pdf_filename}")
            else:
                print(f"PDF report generation failed. Check logs. Only Markdown will be uploaded if configured.")

            # Upload to DigitalOcean Spaces
            print("\n--- DigitalOcean Spaces Upload ---")
            md_url = _upload_to_do_spaces(md_filename)
            if md_url:
                print(f"Markdown report uploaded to: {md_url}")
            else:
                print(f"Markdown report upload failed.")

            if pdf_conversion_success:
                pdf_url = _upload_to_do_spaces(pdf_filename)
                if pdf_url:
                    print(f"PDF report uploaded to: {pdf_url}")
                else:
                    print(f"PDF report upload failed.")
            print("--- End of DigitalOcean Spaces Upload ---\n")

        except Exception as e_write:
            print(f"Error during file operations (save, convert, upload): {e_write}")
            logger.error(f"Error during file operations for report {md_filename}: {e_write}", exc_info=True)
            
        return report_content # Return the original markdown content
    except KeyboardInterrupt:
        print("\nProcess interrupted by user. Partial results may not be available or complete.")
        logger.warning("Report generation interrupted by user.")
        return "Report generation interrupted by user."
    except Exception as e:
        logger.error(f"An unexpected error occurred in run_comprehensive_report for {query_subject}: {str(e)}", exc_info=True)
        print(f"An unexpected error occurred for {query_subject}: {str(e)}")
        return f"Fatal error during report generation for {query_subject}: {str(e)}"

# New function for testing conversion and upload
def test_conversion_and_upload(existing_md_filepath):
    """
    Tests PDF conversion and DigitalOcean Spaces upload for an existing Markdown file.
    """
    logger.info(f"Starting test for PDF conversion and upload for: {existing_md_filepath}")

    if not os.path.exists(existing_md_filepath):
        logger.error(f"Markdown file not found: {existing_md_filepath}")
        print(f"ERROR: Markdown file not found: {existing_md_filepath}")
        return

    base_filename, _ = os.path.splitext(existing_md_filepath)
    pdf_filepath = base_filename + ".pdf"

    # Convert to PDF
    pdf_conversion_success = _convert_md_to_pdf(existing_md_filepath, pdf_filepath)
    if pdf_conversion_success:
        print(f"PDF report generated successfully from {existing_md_filepath} to {pdf_filepath}")
    else:
        print(f"PDF report generation failed for {existing_md_filepath}. Check logs. Only Markdown will be uploaded if configured.")

    # Upload to DigitalOcean Spaces
    print("\n--- DigitalOcean Spaces Upload ---")
    md_url = _upload_to_do_spaces(existing_md_filepath)
    if md_url:
        print(f"Markdown report uploaded to: {md_url}")
    else:
        print(f"Markdown report upload failed for {existing_md_filepath}.")

    if pdf_conversion_success and os.path.exists(pdf_filepath):
        pdf_url = _upload_to_do_spaces(pdf_filepath)
        if pdf_url:
            print(f"PDF report uploaded to: {pdf_url}")
        else:
            print(f"PDF report upload failed for {pdf_filepath}.")
    elif pdf_conversion_success and not os.path.exists(pdf_filepath):
        logger.warning(f"PDF conversion reported success, but PDF file not found at {pdf_filepath} for upload.")
        print(f"PDF file {pdf_filepath} not found for upload despite reported conversion success.")

    print("--- End of DigitalOcean Spaces Upload ---\n")
    logger.info(f"Test for PDF conversion and upload finished for: {existing_md_filepath}")


if __name__ == "__main__":
    try:
        # --- To run the full report generation ---
        report_subject = "NVIDIA (NVDA)" # Or any other subject
        run_comprehensive_report(report_subject)

        # --- To test PDF conversion and upload for an existing MD file ---
        # existing_md_file_to_test = "FINANCE_REPORT_NVIDIA_NVDA_1747824986.md" 
        # script_dir = os.path.dirname(os.path.abspath(__file__))
        # full_md_path = os.path.join(script_dir, existing_md_file_to_test)
        
        # if os.path.exists(full_md_path):
        #     test_conversion_and_upload(full_md_path)
        # else:
        #     print(f"ERROR: Test file not found: {full_md_path}")
        #     logger.error(f"Test file not found: {full_md_path}")

    except Exception as e:
        logger.critical(f"Fatal error in main execution block: {str(e)}", exc_info=True)
        print(f"A critical error occurred in the main execution: {str(e)}")