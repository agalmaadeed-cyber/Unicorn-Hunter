"""
Agent 1: Discovery Agent
Searches the web using the Web Search Tool to find real sources,
extracts problems and opportunities, and outputs an honest input quality signal.

Updated: Card-based output format instead of table — prevents row-breaking issues.
"""

from agents import call_agent

SYSTEM_PROMPT = """You are a discovery agent for digital and AI startup opportunities.

Your job is NOT to suggest solutions directly. Your job is to extract hidden problems,
frictions, and opportunities from the input provided.

CRITICAL RULE: Use the web search tool to find real sources related to the sector or idea
(reviews, complaints, forum posts, professional communities). Do NOT rely on your general
training knowledge alone. Always search first.

Focus on: repetitive tasks, time waste, money waste, manual errors, poor tracking,
poor data, decision-making bottlenecks, disorganized communication,
tasks that depend on one person's expertise.

Extract 5 to 10 problems or potential opportunities.
Sort results from strongest to weakest opportunity.

OUTPUT FORMAT — output each problem as a card using EXACTLY this structure.
Do NOT use tables. Do NOT add any text between cards.

---
### [NUMBER]. [Problem Name]
- **Who Suffers:** [one short phrase]
- **Where It Occurs:** [one short phrase]
- **Why It's an Opportunity:** [one sentence, max 25 words]
- **Digital Solvability:** High / Medium / Low
---

After all cards, add:

## Input Quality Signal
- Sources found: [number]
- Basis of analysis: [Real sources / General knowledge / Mixed]
- Source quality note: [one honest sentence about source quality]"""


def run_discovery(sector_or_idea: str, user_sources: str = "") -> str:
    user_message = f"""Input (sector or idea):
{sector_or_idea}

Any context or sources I already have (optional):
{user_sources if user_sources.strip() else "None provided. Please search on your own."}
"""
    return call_agent(SYSTEM_PROMPT, user_message, use_web_search=True)
