"""
Manual test: per-question field-verification answer boxes (a.9 fix,
cross-project evaluation, 2026-07-22/24).

Verifies the two new pure functions in app.py --
_extract_verification_questions() and _format_verification_answers() --
directly, with zero Streamlit dependency and zero API cost. No real report
is generated; realistic sample report text (matching INITIAL_SYSTEM_PROMPT's
and ADDITIONAL_ROUND_SYSTEM_PROMPT's documented output format) is used
instead.

This repo has no pytest suite and no scripts/ precedent beyond a.5's
manual_test_truncation_warning.py -- same convention followed here: a
standalone script with inline asserts, exit code as the pass/fail signal.

Run: python scripts/manual_test_verification_question_split.py
Exit 0 = all assertions passed.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app

out = []

out.append("=" * 70)
out.append("CASE 1: well-formed initial report -- exactly 3 questions extracted")
out.append("=" * 70)

initial_report = """## MVP Opportunity Report — Initial Analysis

**Idea Name:** Test Idea
**Sector:** Test Sector
**Overall Score (analytical, pre-field verification):** 32/50
**Initial Decision:** Test

---

## Field Verification Questions

1. Would target customers actually pay $10/month for this?
2. Is there an existing competitor already solving this problem well?
3. Can the MVP realistically be built and tested within one week?

Note to reader: This score is analytical and based on model inference — not actual market validation.

---

## Agent Notes

Some additional insight here.
"""

questions = app._extract_verification_questions(initial_report)
assert questions == [
    "Would target customers actually pay $10/month for this?",
    "Is there an existing competitor already solving this problem well?",
    "Can the MVP realistically be built and tested within one week?",
], f"expected exactly the 3 documented questions in order, got: {questions}"
out.append(f"PASS -- extracted exactly 3 questions, in order: {questions}")

out.append("\n" + "=" * 70)
out.append("CASE 2: round report -- 'New Field Verification Questions (Round N)' heading variant")
out.append("=" * 70)

round_report = """## MVP Opportunity Report — Verification Round 2

**Idea Name:** Test Idea
**Cumulative Score After Round 2:** 35/50
**Current Decision:** Test

---

## New Field Verification Questions (Round 3)

1. What was the actual conversion rate in your field test?
2. Which specific objection came up most often?
3. Would a lower price point change the answer?

---

## Agent Notes
"""

round_questions = app._extract_verification_questions(round_report)
assert len(round_questions) == 3, f"expected 3 questions from the Round-N heading variant, got: {round_questions}"
assert round_questions[0] == "What was the actual conversion rate in your field test?"
out.append(f"PASS -- 'New Field Verification Questions (Round N)' heading variant parsed correctly: {round_questions}")

out.append("\n" + "=" * 70)
out.append("CASE 3: no verification-questions section present -- empty list (fallback trigger)")
out.append("=" * 70)

no_section_report = """## MVP Opportunity Report — Initial Analysis

**Idea Name:** Test Idea
**Overall Score (analytical, pre-field verification):** 32/50
**Initial Decision:** Test
"""

assert app._extract_verification_questions(no_section_report) == [], \
    "a report with no verification-questions section must return an empty list, not raise or guess"
out.append("PASS -- missing section correctly returns an empty list (caller falls back to the combined box)")

out.append("\n" + "=" * 70)
out.append("CASE 4: an unrelated numbered list elsewhere in the report is never picked up")
out.append("=" * 70)

report_with_other_numbers = """## MVP Opportunity Report — Initial Analysis

**Idea Name:** Test Idea
**Risks:** 1. market risk, 2. execution risk, 3. timing risk
**Overall Score (analytical, pre-field verification):** 32/50

---

## Field Verification Questions

1. Only this question should be picked up.

---
"""

scoped_questions = app._extract_verification_questions(report_with_other_numbers)
assert scoped_questions == ["Only this question should be picked up."], \
    f"the Risks line's numbers must never leak into the extracted questions, got: {scoped_questions}"
out.append("PASS -- an unrelated numbered list before the section (Risks) is not picked up; only the real section's own numbers are")

out.append("\n" + "=" * 70)
out.append("CASE 5: _format_verification_answers() -- positional, never drops a slot")
out.append("=" * 70)

formatted_all_answered = app._format_verification_answers(["Yes, confirmed.", "No competitor found.", "Yes, one week is enough."])
assert formatted_all_answered == (
    "Q1 answer: Yes, confirmed.\n"
    "Q2 answer: No competitor found.\n"
    "Q3 answer: Yes, one week is enough."
), f"unexpected formatting for all-answered case: {formatted_all_answered!r}"
out.append("PASS -- all 3 answered -> formatted with matching Q1/Q2/Q3 labels")

formatted_partial = app._format_verification_answers(["Yes, confirmed.", "   ", "Yes, one week is enough."])
assert formatted_partial == (
    "Q1 answer: Yes, confirmed.\n"
    "Q2 answer: (not answered)\n"
    "Q3 answer: Yes, one week is enough."
), f"a skipped middle question must stay at its own position, not shift Q3 into Q2's slot: {formatted_partial!r}"
out.append("PASS -- a skipped middle question (Q2) is marked '(not answered)' at its own position, not silently dropped/shifted")

out.append("\n" + "=" * 70)
out.append("ALL ASSERTIONS PASSED")
out.append("=" * 70)

print("\n".join(out))
