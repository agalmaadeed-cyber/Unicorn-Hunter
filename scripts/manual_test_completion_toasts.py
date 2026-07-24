"""
Manual test: active completion toasts (a.10 fix, cross-project evaluation,
2026-07-24).

Before this fix, every genuine step completion in this app (an agent's
live run finishing, or the whole idea pipeline reaching a final decision)
ended in a silent st.rerun() with no signal beyond the page re-rendering.
The fix adds st.toast() immediately before each of these 8
completion-triggering st.rerun() calls (6 individual agent steps + 2
whole-idea-complete paths, the latter added at the founder's explicit
confirmation -- see this a.10 item's VDVE packet, Part 1/3, §0(c)).

This repo has no pytest suite and no AppTest precedent (its existing
scripts/manual_test_*.py files, from a.5 and a.9, test pure functions
only). st.toast() is a Streamlit UI call, invisible to that style of
test, so this introduces streamlit.testing.v1.AppTest here -- same
justification as the sibling vdve and Idea-Dossier repos' own a.10
packets (Parts 1 and 2).

Scope: representative AppTest coverage for 2 of the 8 sites (Discovery,
the first and simplest step; and Skip Verification, one of the two
founder-requested whole-idea-complete paths) plus a baseline check that
no toast fires before any button is clicked. The remaining 6 sites
follow the mechanically identical "st.toast(...) immediately before
st.rerun()" pattern, confirmed by direct diff inspection -- walking the
full pipeline through Problem Framing, Solutions, Evaluation, and both
verification-round paths in AppTest would require chaining many more
stage transitions for a purely mechanical, structurally uniform
addition already fully visible in the diff.

This repo has no ANTHROPIC_API_KEY configured in this sandbox and no
Supabase secrets -- storage falls back to local SQLite
(storage/ideas.db), and every agent call below is monkeypatched, so this
costs nothing and needs no key.

Run: python scripts/manual_test_completion_toasts.py
Exit 0 = all assertions passed.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import patch

from streamlit.testing.v1 import AppTest
from storage.db import init_db, create_idea, update_idea

init_db()

out = []


def _fake_run_discovery(sector_or_idea, user_sources):
    return "### 1. Fake Opportunity\n\nFake discovery output.\n\n## Input Quality Signal\nGood."


def _toast_messages(at):
    return [t.value for t in at.toast]


out.append("=" * 70)
out.append("CASE 1: Discovery completion fires a toast")
out.append("=" * 70)

with patch("agents.discovery.run_discovery", _fake_run_discovery):
    idea_id = create_idea("A fake sector for testing.", "")
    at = AppTest.from_file("app.py")
    at.session_state["idea_id"] = idea_id
    at.session_state["stage"] = "discovery"
    at.run()
    assert at.exception == [], f"exception on Discovery stage load: {at.exception}"

    messages = _toast_messages(at)
    assert "Discovery complete." in messages, messages
    out.append(f"PASS -- Discovery-complete toast fired: {messages}")

out.append("\n" + "=" * 70)
out.append("CASE 2: Skip Verification (whole-idea complete) fires its own toast")
out.append("=" * 70)

sample_report = """## MVP Opportunity Report — Initial Analysis

**Idea Name:** Fake Idea
**Overall Score (analytical, pre-field verification):** 30/50
**Initial Decision:** Test

---

## Field Verification Questions

1. Fake question one?
2. Fake question two?
3. Fake question three?
"""

idea_id2 = create_idea("A fake sector for testing.", "")
update_idea(idea_id2, initial_evaluation=sample_report, initial_score=30)

at2 = AppTest.from_file("app.py")
at2.session_state["idea_id"] = idea_id2
at2.session_state["stage"] = "eval"
at2.run()
assert at2.exception == [], f"exception on Eval stage load: {at2.exception}"

skip_buttons = [b for b in at2.button if "Skip Verification" in b.label]
assert len(skip_buttons) == 1, f"expected exactly 1 'Skip Verification' button, found {len(skip_buttons)}"
skip_buttons[0].click().run()
assert at2.exception == [], f"exception after clicking Skip Verification: {at2.exception}"

messages2 = _toast_messages(at2)
assert "Idea evaluation complete." in messages2, messages2
out.append(f"PASS -- whole-idea-complete toast fired via Skip Verification: {messages2}")

out.append("\n" + "=" * 70)
out.append("CASE 3: no toast fires before any button is clicked")
out.append("=" * 70)

at3 = AppTest.from_file("app.py")
at3.run()
assert _toast_messages(at3) == [], _toast_messages(at3)
out.append("PASS -- no toast on a fresh page load with zero interaction")

out.append("\n" + "=" * 70)
out.append("ALL ASSERTIONS PASSED")
out.append("=" * 70)

print("\n".join(out))
