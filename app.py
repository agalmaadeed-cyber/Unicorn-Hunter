"""
Unicorn Hunter - Main Streamlit Application
Single-page UI with sequential agent pipeline flow.

Bundle A: API key fix (I1/I2), previous stages expanders (I3/U1)
Bundle B: Sidebar filter + sort (U2), idea date display (U2b), compare two ideas (U3)
"""

import os
import re
from datetime import datetime
import streamlit as st

from agents.discovery import run_discovery
from agents.problem_framing import run_problem_framing
from agents.solution_generator import run_solution_generation
from agents.evaluation import run_initial_evaluation, run_reevaluation, run_additional_round

st.set_page_config(page_title="Unicorn Hunter", page_icon="🦄", layout="wide")

# Storage selection: use Supabase if credentials exist, else fall back to SQLite
def _load_storage():
    """
    Try Supabase first. If credentials are missing, fall back to local SQLite.
    Returns (create_idea, update_idea, get_idea, list_ideas, init_db_or_none)
    """
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_KEY")

    # Also check secrets.toml directly
    if not supabase_url or not supabase_key:
        secrets_path = os.path.join(os.path.dirname(__file__), ".streamlit", "secrets.toml")
        if os.path.exists(secrets_path):
            try:
                with open(secrets_path, encoding="utf-8-sig") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("SUPABASE_URL") and not supabase_url:
                            supabase_url = line.split("=", 1)[1].strip().strip('"').strip("'")
                        elif line.startswith("SUPABASE_KEY") and not supabase_key:
                            supabase_key = line.split("=", 1)[1].strip().strip('"').strip("'")
            except Exception:
                pass

    if supabase_url and supabase_key:
        from storage.supabase_db import (
            create_idea, update_idea, get_idea, list_ideas
        )
        return create_idea, update_idea, get_idea, list_ideas, None, "supabase"
    else:
        from storage.db import init_db, create_idea, update_idea, get_idea, list_ideas
        return create_idea, update_idea, get_idea, list_ideas, init_db, "sqlite"

create_idea, update_idea, get_idea, list_ideas, _init_db, _storage_backend = _load_storage()
if _init_db:
    _init_db()

# ---------- Session state init ----------
defaults = {
    "idea_id": None,
    "stage": "input",
    "selected_problem": "",
    "compare_ids": [],
    "view": "pipeline",  # pipeline | compare
}
for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val


def reset_session():
    st.session_state.idea_id = None
    st.session_state.stage = "input"
    st.session_state.selected_problem = ""
    st.session_state.compare_ids = []
    st.session_state.view = "pipeline"


def format_date(iso_str: str) -> str:
    """Convert ISO datetime string to readable date."""
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.strftime("%d %b %Y, %H:%M")
    except Exception:
        return iso_str or "—"


def extract_decision_and_score(report_text: str) -> tuple:
    """
    Extract decision (Build/Test/Park/Reject) and score (XX/50) from report text.
    Returns (decision, score) or (None, None).
    """
    decision = None
    score = None

    decision_patterns = [
        r"(?:Final\s+)?Decision[:\s*_]+\**(Build|Test|Park|Reject)\**",
        r"\*\*(?:Final\s+)?Decision[:\s*_]+\**(Build|Test|Park|Reject)",
        r"(?:Build|Test|Park|Reject)(?=\s*$|\s*\n)",
    ]
    for pattern in decision_patterns:
        match = re.search(pattern, report_text, re.IGNORECASE | re.MULTILINE)
        if match:
            decision = match.group(1) if match.lastindex else match.group(0)
            decision = decision.strip().capitalize()
            break

    score_patterns = [
        r"(?:Final\s+)?(?:Overall\s+)?Score[^:]*:\s*\**(\d+)/50",
        r"(\d+)\s*/\s*50",
    ]
    for pattern in score_patterns:
        match = re.search(pattern, report_text, re.IGNORECASE)
        if match:
            score = int(match.group(1))
            break

    return decision, score


def _extract_verification_questions(report_text: str) -> list:
    """
    Deterministically parse the numbered verification questions out of an
    evaluation report's own markdown structure (a.9 fix, cross-project
    evaluation, 2026-07-22/24). Both INITIAL_SYSTEM_PROMPT and
    ADDITIONAL_ROUND_SYSTEM_PROMPT instruct the model to emit a
    "## Field Verification Questions" (or "## New Field Verification
    Questions (Round N)") section with a plain numbered list ("1. 2. 3.").
    Same class of deterministic report-parsing already trusted in this repo
    (see extract_decision_and_score() above), scoped strictly to the
    matched section's own text so it can never accidentally pick up an
    unrelated numbered list elsewhere in the report.

    Returns a list of question strings, in order. Returns an empty list if
    the section or its numbered items can't be found -- callers MUST treat
    an empty list as "fall back to a single combined answer box", not as
    an error; a model that ever deviates from the documented format
    degrades safely to the old behavior instead of crashing or silently
    mis-parsing.
    """
    section_match = re.search(
        r"##\s*(?:New\s+)?Field Verification Questions[^\n]*\n(.*?)(?=\n##|\Z)",
        report_text,
        re.IGNORECASE | re.DOTALL,
    )
    if not section_match:
        return []

    section_text = section_match.group(1)
    questions = re.findall(r"^\s*\d+\.\s*(.+)$", section_text, re.MULTILINE)
    return [q.strip() for q in questions if q.strip()]


def _format_verification_answers(individual_answers: list) -> str:
    """
    Recombine per-question answer boxes back into a single string for the
    agent-facing user_answers/new_answers payload (a.9 fix). Always
    includes every slot by position, labeled "Q1 answer:", "Q2 answer:",
    etc. -- an unanswered question is written out as "(not answered)"
    rather than silently dropped, so the numbering can never drift and
    misalign an answer with the wrong question if the founder skips one.
    """
    return "\n".join(
        f"Q{i} answer: {a.strip() if a.strip() else '(not answered)'}"
        for i, a in enumerate(individual_answers, start=1)
    )


def show_previous_stages(idea: dict, current_stage: str):
    """
    Display all completed previous stages as collapsed expanders.
    Allows user to read any previous output without losing current stage.
    """
    stages_order = ["discovery", "problem", "solutions", "eval", "reeval", "done"]
    current_index = stages_order.index(current_stage) if current_stage in stages_order else 0

    if current_index == 0:
        return

    st.markdown("---")
    st.caption("📂 Previous stages — click to expand and read")

    if current_index > 0 and idea.get("discovery_output"):
        with st.expander("Step 2 — Discovery Agent output", expanded=False):
            st.markdown(idea["discovery_output"])

    if current_index > 1 and idea.get("problem_card"):
        with st.expander("Step 3 — Problem Card", expanded=False):
            st.markdown(idea["problem_card"])

    if current_index > 2 and idea.get("solutions_output"):
        with st.expander("Step 4 — Solution Options", expanded=False):
            st.markdown(idea["solutions_output"])

    if current_index > 3 and idea.get("initial_evaluation"):
        with st.expander("Step 5 — Initial Evaluation Report", expanded=False):
            st.markdown(idea["initial_evaluation"])
        if idea.get("user_answers"):
            with st.expander("Step 5 — Your Field Verification Answers", expanded=False):
                st.markdown(idea["user_answers"])

    if current_index > 4 and idea.get("final_evaluation"):
        with st.expander("Step 6 — Re-evaluation After Field Verification", expanded=False):
            st.markdown(idea["final_evaluation"])

    st.markdown("---")


def decision_badge(decision: str) -> str:
    icons = {"Build": "🟢", "Test": "🟡", "Park": "🔵", "Reject": "🔴"}
    return icons.get(decision, "⚪")


# ---------- Sidebar ----------
with st.sidebar:
    st.header("🦄 Unicorn Hunter")
    storage_icon = "☁️ Supabase" if _storage_backend == "supabase" else "💾 Local SQLite"
    st.caption(f"Idea Generator & Validator · {storage_icon}")

    if st.button("➕ New Idea", use_container_width=True):
        reset_session()
        st.rerun()

    st.divider()

    # --- Filter & Sort controls ---
    all_ideas = list_ideas()

    filter_decision = st.selectbox(
        "Filter by decision",
        ["All", "Build", "Test", "Park", "Reject", "In Progress"],
        index=0,
    )

    sort_by = st.selectbox(
        "Sort by",
        ["Newest first", "Oldest first", "Highest score", "Lowest score"],
        index=0,
    )

    # Apply filter
    if filter_decision == "In Progress":
        filtered = [r for r in all_ideas if r.get("status") != "completed"]
    elif filter_decision != "All":
        filtered = [r for r in all_ideas if (r.get("decision") or "").lower() == filter_decision.lower()]
    else:
        filtered = all_ideas

    # Apply sort
    def sort_key(r):
        if "score" in sort_by.lower():
            s = r.get("final_score") or r.get("initial_score") or 0
            return s if "highest" in sort_by.lower() else -s
        return r["id"] if "oldest" in sort_by.lower() else -r["id"]

    filtered = sorted(filtered, key=sort_key)

    st.caption(f"Showing {len(filtered)} of {len(all_ideas)} ideas")
    st.divider()

    # --- Compare mode toggle ---
    compare_mode = st.toggle("Select ideas to compare", value=False)

    if compare_mode and len(st.session_state.compare_ids) == 2:
        if st.button("🔍 Compare Selected Ideas", type="primary", use_container_width=True):
            st.session_state.view = "compare"
            st.rerun()
    elif compare_mode:
        remaining = 2 - len(st.session_state.compare_ids)
        st.caption(f"Select {remaining} more idea(s) to compare")

    st.subheader("Idea History")

    for row in filtered:
        idea_id = row["id"]
        label = f"#{idea_id} — {row['sector_or_idea'][:30]}"
        decision = row.get("decision") or "—"
        score = row.get("final_score") or row.get("initial_score") or "—"
        status = row.get("status") or "in progress"
        date_str = format_date(row.get("created_at", ""))

        if status == "completed":
            score_str = f"{score}/50" if score != "—" else "—"
            badge = f"{decision_badge(decision)} {decision} | {score_str}"
        else:
            badge = "🔄 in progress"

        if compare_mode:
            is_checked = idea_id in st.session_state.compare_ids
            col1, col2 = st.columns([1, 4])
            with col1:
                checked = st.checkbox("", value=is_checked, key=f"cmp_{idea_id}")
                if checked and idea_id not in st.session_state.compare_ids:
                    if len(st.session_state.compare_ids) < 2:
                        st.session_state.compare_ids.append(idea_id)
                        st.rerun()
                elif not checked and idea_id in st.session_state.compare_ids:
                    st.session_state.compare_ids.remove(idea_id)
                    st.rerun()
            with col2:
                st.caption(f"{label}\n{badge}\n📅 {date_str}")
        else:
            if st.button(
                f"{label}\n{badge}\n📅 {date_str}",
                key=f"hist_{idea_id}",
                use_container_width=True,
            ):
                st.session_state.compare_ids = []
                st.session_state.view = "pipeline"
                st.session_state.idea_id = idea_id
                idea = get_idea(idea_id)
                if idea.get("final_evaluation"):
                    st.session_state.stage = "done"
                elif idea.get("initial_evaluation"):
                    st.session_state.stage = "reeval"
                elif idea.get("solutions_output"):
                    st.session_state.stage = "eval"
                elif idea.get("problem_card"):
                    st.session_state.stage = "solutions"
                elif idea.get("discovery_output"):
                    st.session_state.stage = "problem"
                else:
                    st.session_state.stage = "discovery"
                st.rerun()

# ============================================================
# COMPARE VIEW
# ============================================================
if st.session_state.view == "compare":
    ids = st.session_state.compare_ids
    if len(ids) != 2:
        st.warning("Please select exactly 2 ideas to compare.")
        if st.button("← Back"):
            st.session_state.view = "pipeline"
            st.rerun()
    else:
        idea_a = get_idea(ids[0])
        idea_b = get_idea(ids[1])

        st.title("🔍 Idea Comparison")

        if st.button("← Back to Pipeline"):
            st.session_state.view = "pipeline"
            st.session_state.compare_ids = []
            st.rerun()

        # Summary metrics side by side
        col_a, col_b = st.columns(2)

        def render_idea_summary(col, idea):
            with col:
                decision = idea.get("decision") or "—"
                score = idea.get("final_score") or idea.get("initial_score") or "—"
                date_str = format_date(idea.get("created_at", ""))
                st.subheader(f"#{idea['id']} — {idea['sector_or_idea'][:50]}")
                st.caption(f"📅 Created: {date_str}")
                m1, m2 = st.columns(2)
                with m1:
                    st.metric("Decision", f"{decision_badge(decision)} {decision}")
                with m2:
                    st.metric("Score", f"{score}/50" if score != "—" else "—")

        render_idea_summary(col_a, idea_a)
        render_idea_summary(col_b, idea_b)

        st.divider()

        # Side-by-side full reports
        sections = [
            ("Discovery Output", "discovery_output"),
            ("Problem Card", "problem_card"),
            ("Solutions", "solutions_output"),
            ("Initial Evaluation", "initial_evaluation"),
            ("Field Answers", "user_answers"),
            ("Final Evaluation", "final_evaluation"),
        ]

        for section_title, field in sections:
            content_a = idea_a.get(field)
            content_b = idea_b.get(field)
            if content_a or content_b:
                with st.expander(f"📄 {section_title}", expanded=False):
                    c1, c2 = st.columns(2)
                    with c1:
                        st.caption(f"Idea #{idea_a['id']}")
                        st.markdown(content_a or "— Not available —")
                    with c2:
                        st.caption(f"Idea #{idea_b['id']}")
                        st.markdown(content_b or "— Not available —")

# ============================================================
# PIPELINE VIEW
# ============================================================
else:
    st.title("🦄 Unicorn Hunter")
    st.caption("Internal multi-agent system for generating and validating digital & AI startup ideas")

    # ---------- Stage 1: Input ----------
    if st.session_state.stage == "input":
        st.subheader("Step 1 — Start a New Idea")

        sector_or_idea = st.text_area(
            "Idea or sector to explore",
            placeholder="Example: I want to explore problems in small coffee shops that can be solved with a digital product",
            height=100,
        )
        user_sources = st.text_area(
            "Your own context or sources (optional)",
            placeholder="Any notes, links, or text you already have — the system will complete with web search",
            height=100,
        )

        if st.button("🚀 Start Analysis", type="primary", disabled=not sector_or_idea.strip()):
            idea_id = create_idea(sector_or_idea, user_sources)
            st.session_state.idea_id = idea_id
            st.session_state.stage = "discovery"
            st.rerun()

    # ---------- Stage 2: Discovery ----------
    elif st.session_state.stage == "discovery":
        idea = get_idea(st.session_state.idea_id)
        st.subheader("Step 2 — Discovery Agent (searching the web)")
        st.caption(f"📅 Created: {format_date(idea.get('created_at', ''))}")

        if not idea.get("discovery_output"):
            with st.spinner("Searching the web and extracting opportunities..."):
                output = run_discovery(idea["sector_or_idea"], idea["user_sources"] or "")
                update_idea(idea["id"], discovery_output=output)
            st.rerun()
        else:
            # Parse cards from discovery output
            raw = idea["discovery_output"]

            # Split into individual cards by ### delimiter
            card_blocks = re.split(r'(?=###\s+\d+\.)', raw)
            cards = []
            footer = ""
            for block in card_blocks:
                block = block.strip()
                if not block:
                    continue
                if block.startswith("###"):
                    # Extract card title for button label
                    first_line = block.split("\n")[0]
                    title = re.sub(r"^###\s+\d+\.\s*", "", first_line).strip()
                    cards.append({"title": title, "content": block})
                elif block.startswith("## Input Quality Signal"):
                    footer = block

            if cards:
                st.info("Select the problem you want to investigate by clicking on a card.")
                selected = st.session_state.get("selected_card_content", "")

                for i, card in enumerate(cards):
                    is_selected = selected == card["content"]
                    with st.container():
                        col1, col2 = st.columns([5, 1])
                        with col1:
                            st.markdown(card["content"])
                        with col2:
                            label = "✅ Selected" if is_selected else "Select"
                            btn_type = "primary" if is_selected else "secondary"
                            if st.button(label, key=f"card_{i}", type=btn_type):
                                st.session_state.selected_card_content = card["content"]
                                st.rerun()
                        st.divider()

                if footer:
                    with st.expander("📊 Input Quality Signal", expanded=False):
                        st.markdown(footer)

                selected_content = st.session_state.get("selected_card_content", "")
                if st.button("➡️ Continue to Problem Framing", type="primary",
                             disabled=not selected_content):
                    st.session_state.selected_problem = selected_content
                    st.session_state.stage = "problem"
                    st.rerun()
            else:
                # Fallback: show raw output with manual text input
                st.markdown(raw)
                st.divider()
                st.info("Copy the problem you want to continue with into the field below.")
                selected_problem = st.text_area("Selected problem to investigate", height=120)
                if st.button("➡️ Continue to Problem Framing",
                             disabled=not selected_problem.strip()):
                    st.session_state.selected_problem = selected_problem
                    st.session_state.stage = "problem"
                    st.rerun()

    # ---------- Stage 3: Problem Framing ----------
    elif st.session_state.stage == "problem":
        idea = get_idea(st.session_state.idea_id)
        st.subheader("Step 3 — Problem Framing Agent")
        st.caption(f"📅 Created: {format_date(idea.get('created_at', ''))}")
        show_previous_stages(idea, "problem")

        if st.button("🔍 Generate Problem Card"):
            with st.spinner("Analyzing the problem..."):
                output = run_problem_framing(
                    st.session_state.selected_problem, idea["sector_or_idea"]
                )
                update_idea(idea["id"], problem_card=output)
            st.rerun()

        idea = get_idea(st.session_state.idea_id)
        if idea.get("problem_card"):
            st.markdown(idea["problem_card"])
            st.divider()
            if st.button("➡️ Continue to Solution Generation", type="primary"):
                st.session_state.stage = "solutions"
                st.rerun()

    # ---------- Stage 4: Solution Generation ----------
    elif st.session_state.stage == "solutions":
        idea = get_idea(st.session_state.idea_id)
        st.subheader("Step 4 — Solution Generator Agent")
        st.caption(f"📅 Created: {format_date(idea.get('created_at', ''))}")
        show_previous_stages(idea, "solutions")

        if not idea.get("solutions_output"):
            with st.spinner("Generating diverse solutions..."):
                output = run_solution_generation(idea["problem_card"])
                update_idea(idea["id"], solutions_output=output)
            st.rerun()
        else:
            st.markdown(idea["solutions_output"])
            st.divider()
            if st.button("➡️ Continue to Initial Evaluation", type="primary"):
                st.session_state.stage = "eval"
                st.rerun()

    # ---------- Stage 5: Initial Evaluation ----------
    elif st.session_state.stage == "eval":
        idea = get_idea(st.session_state.idea_id)
        st.subheader("Step 5 — Evaluation Agent (Initial Report)")
        st.caption(f"📅 Created: {format_date(idea.get('created_at', ''))}")
        show_previous_stages(idea, "eval")

        if not idea.get("initial_evaluation"):
            with st.spinner("Evaluating solutions and generating verification questions..."):
                output = run_initial_evaluation(idea["problem_card"], idea["solutions_output"])
                decision, score = extract_decision_and_score(output)
                update_idea(idea["id"], initial_evaluation=output, initial_score=score)
            st.rerun()
        else:
            st.warning("⚠️ This is an analytical report based on model inference — NOT actual market validation.")
            st.markdown(idea["initial_evaluation"])
            st.divider()
            st.subheader("Field Verification Answers")
            # a.9 fix (cross-project evaluation, 2026-07-22/24): a separate
            # answer box per question, deterministically parsed out of the
            # report itself, instead of one combined free-text box for all
            # 3 questions. Falls back to the original single combined box
            # if the report ever deviates from the documented format.
            verification_questions = _extract_verification_questions(idea["initial_evaluation"])
            if verification_questions:
                st.caption("Go verify in the field, then enter what you found for each question.")
                individual_answers = []
                for q_i, q_text in enumerate(verification_questions, start=1):
                    st.markdown(f"**Q{q_i}.** {q_text}")
                    individual_answers.append(
                        st.text_area(f"Your answer to Q{q_i}", height=80, key=f"user_answer_q{q_i}")
                    )
                answers = _format_verification_answers(individual_answers)
                has_any_answer = any(a.strip() for a in individual_answers)
            else:
                st.caption("Go verify in the field, then enter what you found.")
                answers = st.text_area("Your answers", height=150, key="user_answers_input")
                has_any_answer = bool(answers.strip())

            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ Submit Answers & Re-evaluate", type="primary",
                             disabled=not has_any_answer):
                    update_idea(idea["id"], user_answers=answers)
                    st.session_state.stage = "reeval"
                    st.rerun()
            with col2:
                if st.button("⏭️ Skip Verification — Keep Initial Report Only"):
                    idea = get_idea(st.session_state.idea_id)
                    decision, score = extract_decision_and_score(idea["initial_evaluation"])
                    update_idea(idea["id"], status="completed", decision=decision, final_score=score)
                    st.session_state.stage = "done"
                    st.rerun()

    # ---------- Stage 6: Re-evaluation (multi-round) ----------
    elif st.session_state.stage == "reeval":
        import json as _json

        idea = get_idea(st.session_state.idea_id)

        # Load verification rounds history
        rounds_history = []
        if idea.get("verification_rounds"):
            try:
                rounds_history = _json.loads(idea["verification_rounds"])
            except Exception:
                rounds_history = []

        current_round = len(rounds_history) + 1
        st.subheader(f"Step 6 — Field Verification Round {current_round}")
        st.caption(f"📅 Created: {format_date(idea.get('created_at', ''))}")
        show_previous_stages(idea, "reeval")

        # Show all previous rounds as expanders
        if rounds_history:
            st.caption(f"📋 {len(rounds_history)} previous round(s) completed")
            for i, r in enumerate(rounds_history, start=1):
                with st.expander(f"Round {i} — Report & Answers", expanded=False):
                    st.markdown(f"**Your Answers:**\n{r.get('answers', '—')}")
                    st.divider()
                    st.markdown(r.get("report", "—"))

        # Run first re-evaluation if not done yet
        if not idea.get("final_evaluation"):
            with st.spinner("Updating evaluation based on your answers..."):
                output = run_reevaluation(
                    idea["initial_evaluation"],
                    "See the 'Field Verification Questions' section in the initial report above.",
                    idea["user_answers"],
                )
                decision, score = extract_decision_and_score(output)
                first_round = {
                    "round": 1,
                    "answers": idea.get("user_answers", ""),
                    "report": output,
                }
                rounds_history = [first_round]
                update_idea(
                    idea["id"],
                    final_evaluation=output,
                    final_score=score,
                    decision=decision,
                    status="in_progress",
                    verification_rounds=_json.dumps(rounds_history, ensure_ascii=False),
                )
            st.rerun()
        else:
            st.markdown(idea["final_evaluation"])
            st.divider()
            st.subheader("What would you like to do next?")

            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Run another verification round**")
                # a.9 fix (cross-project evaluation, 2026-07-22/24): same
                # per-question split as Step 5's initial verification,
                # parsed from this round's own report (which ends with the
                # NEXT round's "## New Field Verification Questions"
                # section per ADDITIONAL_ROUND_SYSTEM_PROMPT). Falls back
                # to the original single combined box if unparseable.
                round_questions = _extract_verification_questions(idea["final_evaluation"])
                if round_questions:
                    individual_round_answers = []
                    for q_i, q_text in enumerate(round_questions, start=1):
                        st.markdown(f"**Q{q_i}.** {q_text}")
                        individual_round_answers.append(
                            st.text_area(
                                f"Your answer to Q{q_i}",
                                height=80,
                                key=f"new_answer_round_{current_round}_q{q_i}",
                            )
                        )
                    new_answers = _format_verification_answers(individual_round_answers)
                    has_any_round_answer = any(a.strip() for a in individual_round_answers)
                else:
                    new_answers = st.text_area(
                        f"Your answers for Round {current_round}",
                        height=150,
                        key=f"new_answers_round_{current_round}",
                    )
                    has_any_round_answer = bool(new_answers.strip())
                if st.button(
                    f"🔄 Run Round {current_round}",
                    type="primary",
                    disabled=not has_any_round_answer,
                ):
                    with st.spinner(f"Running verification round {current_round}..."):
                        output = run_additional_round(
                            initial_report=idea["initial_evaluation"],
                            rounds_history=rounds_history,
                            new_answers=new_answers,
                            round_number=current_round,
                        )
                        decision, score = extract_decision_and_score(output)
                        new_round = {
                            "round": current_round,
                            "answers": new_answers,
                            "report": output,
                        }
                        rounds_history.append(new_round)
                        update_idea(
                            idea["id"],
                            final_evaluation=output,
                            final_score=score,
                            decision=decision,
                            status="in_progress",
                            verification_rounds=_json.dumps(rounds_history, ensure_ascii=False),
                        )
                    st.rerun()

            with col2:
                st.markdown("**Finalize this idea**")
                st.caption("Close verification and move to final report.")
                if st.button("✅ Finalize & View Final Report", type="secondary"):
                    idea = get_idea(st.session_state.idea_id)
                    decision, score = extract_decision_and_score(idea["final_evaluation"])
                    update_idea(idea["id"], status="completed", decision=decision, final_score=score)
                    st.session_state.stage = "done"
                    st.rerun()

    # ---------- Stage 7: Final Report ----------
    elif st.session_state.stage == "done":
        idea = get_idea(st.session_state.idea_id)
        st.subheader("✅ Final Report")
        st.caption(f"📅 Created: {format_date(idea.get('created_at', ''))}")

        decision = idea.get("decision") or "—"
        score = idea.get("final_score") or idea.get("initial_score") or "—"

        col1, col2 = st.columns(2)
        with col1:
            st.metric("Decision", f"{decision_badge(decision)} {decision}")
        with col2:
            st.metric("Score", f"{score}/50" if score != "—" else "—")

        st.divider()
        show_previous_stages(idea, "done")

        final_text = idea.get("final_evaluation") or idea.get("initial_evaluation")
        st.markdown(final_text)

        md_content = f"""# MVP Opportunity Report — Unicorn Hunter

**Idea ID:** {idea['id']}
**Created:** {format_date(idea.get('created_at', ''))}
**Original Input:** {idea['sector_or_idea']}
**Decision:** {decision}
**Final Score:** {score}/50

---

## Discovery Agent Output
{idea.get('discovery_output', '—')}

---

## Problem Card
{idea.get('problem_card', '—')}

---

## Proposed Solutions
{idea.get('solutions_output', '—')}

---

## Initial Evaluation (Analytical)
{idea.get('initial_evaluation', '—')}

---

## Field Verification Answers
{idea.get('user_answers', '—')}

---

## Final Evaluation (After Field Verification)
{idea.get('final_evaluation', 'Field verification was not completed for this idea.')}
"""

        st.download_button(
            "⬇️ Download Full Report as Markdown",
            data=md_content,
            file_name=f"unicorn_hunter_idea_{idea['id']}.md",
            mime="text/markdown",
            type="primary",
        )

        if st.button("➕ Start New Idea"):
            reset_session()
            st.rerun()
