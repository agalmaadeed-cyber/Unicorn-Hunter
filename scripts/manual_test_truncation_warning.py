"""
Manual test: agents.call_agent()'s max_tokens truncation warning (a.5 fix).

Verifies the fix's actual logic (agents/__init__.py::call_agent appending a
visible warning when response.stop_reason == "max_tokens") and
solution_generator's raised max_tokens, without making any real API call --
the Anthropic client is monkeypatched with a fake that returns a canned
response object, so this costs nothing to run.

This repo has no existing test/verification convention (no pytest, no
scripts/manual_test_*.py precedent) -- this script follows the pattern
already established in the sibling Idea-Dossier repo for the same reason:
a standalone script with inline asserts, exit code as the pass/fail signal.

Run: python scripts/manual_test_truncation_warning.py
Exit 0 = all assertions passed.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import agents


class _FakeTextBlock:
    def __init__(self, text):
        self.text = text


class _FakeResponse:
    def __init__(self, text, stop_reason):
        self.content = [_FakeTextBlock(text)]
        self.stop_reason = stop_reason


class _FakeMessages:
    def __init__(self, response):
        self._response = response
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        return self._response


class _FakeClient:
    def __init__(self, response):
        self.messages = _FakeMessages(response)


def _run_with_fake_response(text, stop_reason):
    fake_response = _FakeResponse(text, stop_reason)
    fake_client = _FakeClient(fake_response)
    original_get_client = agents.get_client
    agents.get_client = lambda: fake_client
    try:
        return agents.call_agent("system prompt", "user message"), fake_client
    finally:
        agents.get_client = original_get_client


out = []

out.append("=" * 70)
out.append("CASE 1: normal completion (stop_reason='end_turn') -- no warning expected")
out.append("=" * 70)
result_normal, _ = _run_with_fake_response("| Solution A | ... |", "end_turn")
assert "max_tokens" not in result_normal.lower() and "cut off" not in result_normal.lower(), \
    f"Warning leaked into a normal, non-truncated response: {result_normal!r}"
assert result_normal == "| Solution A | ... |", f"Unexpected mutation of a clean response: {result_normal!r}"
out.append("PASS -- clean response returned unmodified, no warning appended")

out.append("\n" + "=" * 70)
out.append("CASE 2: truncated completion (stop_reason='max_tokens') -- warning expected")
out.append("=" * 70)
truncated_text = "| Solution A | ... | Solution B | (cut off mid-row"
result_truncated, _ = _run_with_fake_response(truncated_text, "max_tokens")
assert result_truncated.startswith(truncated_text), \
    "Original (truncated) model text must be preserved, not replaced"
assert "max_tokens" in result_truncated.lower() and "cut off" in result_truncated.lower(), \
    f"Expected a visible truncation warning appended, got: {result_truncated!r}"
out.append("PASS -- original truncated text preserved, visible warning appended")
out.append(f"\nFull warned output:\n{result_truncated}")

out.append("\n" + "=" * 70)
out.append("CASE 3: run_solution_generation() must request max_tokens=8000 (was 4000)")
out.append("=" * 70)
from agents.solution_generator import run_solution_generation

fake_response = _FakeResponse("| table |", "end_turn")
fake_client = _FakeClient(fake_response)
original_get_client = agents.get_client
agents.get_client = lambda: fake_client
try:
    run_solution_generation("fake problem card")
finally:
    agents.get_client = original_get_client
assert fake_client.messages.last_kwargs["max_tokens"] == 8000, \
    f"Expected max_tokens=8000, got {fake_client.messages.last_kwargs.get('max_tokens')}"
out.append("PASS -- run_solution_generation() requests max_tokens=8000")

out.append("\n" + "=" * 70)
out.append("ALL ASSERTIONS PASSED")
out.append("=" * 70)

print("\n".join(out))
