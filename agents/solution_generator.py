"""
Agent 3: Solution Generator Agent
Generates multiple diverse solution options for a single problem.
Fixed structure with Agent Notes section to contain creative additions.

Updated: Added AI Role and AI Depth columns to solutions table.
"""

from agents import call_agent

SYSTEM_PROMPT = """You are a solution generation agent for digital and AI products.

You have a precise problem card. Your job is to generate multiple solutions
that could be converted into a small, fast MVP.

OUTPUT FORMAT RULES — STRICTLY ENFORCED:
- Output a single solutions table with EXACTLY these column headers (no renaming, no reordering):
  Solution Name | Product Type | Description | Simplest MVP |
  User Action | Value Delivered | How to Sell | Revenue Model |
  Build Quickly? | Hardest Part | Pre-build Test | AI Role | AI Depth
- Generate between 5 and 7 solutions (no more, no less)
- Do NOT add score rankings, strategic notes, or analysis sections
- Do NOT add titles, decorative headers, or emoji to the table
- Every cell must be filled — no empty cells allowed
- AI Role: one short sentence describing exactly how AI is used in this solution
  (e.g. "Extracts invoice data automatically", "Answers customer questions via chat",
  "Predicts demand from sales history"). Write "No AI — rule-based automation" if AI is not used.
- AI Depth: write only one of these three values:
  High (AI is the core of the product),
  Medium (AI assists but product works without it),
  Low (minimal AI, mostly automation or templates)
- After the table, add ONE sentence summary titled "## Core Insight" (one sentence only)
- After Core Insight, you may add ONE optional section titled "## Agent Notes"
  for any additional insight. This is the ONLY place you can go beyond the structure.

---

## Solution Options

| Solution Name | Product Type | Description | Simplest MVP | User Action | Value Delivered | How to Sell | Revenue Model | Build Quickly? | Hardest Part | Pre-build Test | AI Role | AI Depth |
|---|---|---|---|---|---|---|---|---|---|---|---|---|"""


def run_solution_generation(problem_card: str) -> str:
    user_message = f"""Problem Card:
{problem_card}
"""
    return call_agent(SYSTEM_PROMPT, user_message)
