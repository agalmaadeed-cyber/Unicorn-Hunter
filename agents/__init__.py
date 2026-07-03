"""
Unicorn Hunter - Shared agent utilities.
Provides unified call function for Anthropic API with Web Search Tool support.

Bundle A fix (I1/I2):
- Reads API key from environment variable first (most reliable on Windows)
- Falls back to secrets.toml read with explicit UTF-8 encoding to strip BOM
- Clear error message guides user to correct setup method
"""

import os
import anthropic

MODEL = "claude-sonnet-4-6"

LANGUAGE_INSTRUCTION = (
    "IMPORTANT: Detect the language of the user's input and respond entirely in that same language. "
    "If the input is in Arabic, respond in Arabic. If in English, respond in English. "
    "Never switch languages mid-response."
)


def get_client():
    # Priority 1: environment variable (most reliable, no encoding issues)
    api_key = os.environ.get("ANTHROPIC_API_KEY")

    # Priority 2: secrets.toml read with explicit UTF-8 to handle BOM on Windows
    if not api_key:
        secrets_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            ".streamlit", "secrets.toml"
        )
        if os.path.exists(secrets_path):
            try:
                with open(secrets_path, encoding="utf-8-sig") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("ANTHROPIC_API_KEY"):
                            api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                            break
            except Exception:
                pass

    # Priority 3: st.secrets (Streamlit Cloud deployment)
    if not api_key:
        try:
            import streamlit as st
            api_key = st.secrets.get("ANTHROPIC_API_KEY")
        except Exception:
            pass

    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY not found.\n"
            "Option 1 (recommended on Windows): set it in PowerShell before running:\n"
            '  $env:ANTHROPIC_API_KEY="sk-ant-..."\n'
            "Option 2: add it to .streamlit/secrets.toml:\n"
            '  ANTHROPIC_API_KEY = "sk-ant-..."'
        )
    return anthropic.Anthropic(api_key=api_key)


def call_agent(system_prompt: str, user_message: str, use_web_search: bool = False,
               max_tokens: int = 4000) -> str:
    """
    Unified call function for all agents.
    Injects language instruction into every system prompt automatically.
    Web search enabled only for Discovery Agent.
    """
    client = get_client()

    full_system_prompt = f"{LANGUAGE_INSTRUCTION}\n\n{system_prompt}"

    kwargs = {
        "model": MODEL,
        "max_tokens": max_tokens,
        "system": full_system_prompt,
        "messages": [{"role": "user", "content": user_message}],
    }

    if use_web_search:
        kwargs["tools"] = [{
            "type": "web_search_20250305",
            "name": "web_search",
            "max_uses": 5,
        }]

    response = client.messages.create(**kwargs)

    text_parts = [block.text for block in response.content if hasattr(block, "text")]
    return "\n".join(text_parts).strip()
