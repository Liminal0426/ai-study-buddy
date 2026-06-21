"""Self-evolution module for AI Study Buddy.

After every interaction, analyzes the conversation and:
1. Extracts concepts the user worked on
2. Tracks success/failure patterns
3. Updates user knowledge state
4. Auto-discovers user preferences
5. Suggests what to learn next

Inspired by Hermes Agent's background_review.py — an automatic
after-turn reflection that improves the system over time.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from study_buddy.memory import (
    ConceptState, MemoryStore, ProblemRecord, UserPref, get_store,
)
from study_buddy.solver import _api_request

logger = logging.getLogger(__name__)


# ── Concept extraction ─────────────────────────────────────────────────

_CONCEPT_PROMPT = """\
Extract learning-relevant data from this study interaction.

Input:
  Problem: {problem}
  Explanation: {explanation}
  Subject: {subject}

Output ONLY valid JSON with NO markdown fences, NO commentary:

1. "concepts": list of {{"name": str, "level": int, "notes": str}}
   Levels: 0=not_mathed, 1=seen, 2=learning, 3=got_it, 4=mastered
   Base the level on the user's understanding shown in the interaction.

2. "difficulty": int 1-5 (how hard was this problem? 3=average)

3. "next_topics": list of str (what should user study next based on
   gaps visible in this problem? Empty if unclear.)

4. "user_preferences": list of {{"key": str, "value": str}}
   Things like: learning_style=visual, pace=slow, format=pdf, etc.
   Infer from the user's behaviour. Empty if unsure.

Example output:
{{"concepts": [{{"name": "二次函数", "level": 2, "notes": "会画基本图像但不会求顶点坐标"}}],
  "difficulty": 3,
  "next_topics": ["配方法", "顶点式"],
  "user_preferences": [{{"key": "learning_style", "value": "visual"}}]}}
"""


def analyze_interaction(
    problem: str,
    explanation: str,
    subject: str,
    success: bool = True,
) -> Dict[str, Any]:
    """Post-interaction analysis: extract concepts, preferences, next steps.

    Runs a cheap LLM call to analyze what happened and update memory.
    Returns the analysis dict.
    """
    try:
        raw = _api_request(
            [
                {
                    "role": "system",
                    "content": _CONCEPT_PROMPT.format(
                        problem=problem[:500],
                        explanation=explanation[:1000],
                        subject=subject,
                    ),
                },
                {"role": "user", "content": "Analyze this interaction."},
            ],
            max_tokens=1024,
            temperature=0.1,
        )
        # Strip code fences if any
        raw = re.sub(r"```(?:json)?\s*", "", raw).strip()
        analysis = json.loads(raw)
    except Exception as e:
        logger.debug("Self-evolution analysis failed: %s", e)
        return {
            "concepts": [],
            "difficulty": 3,
            "next_topics": [],
            "user_preferences": [],
        }

    # Validate structure
    if not isinstance(analysis, dict):
        return {
            "concepts": [],
            "difficulty": 3,
            "next_topics": [],
            "user_preferences": [],
        }
    return analysis


# ── Memory update ──────────────────────────────────────────────────────

def process_interaction(
    problem: str,
    explanation: str,
    subject: str,
    success: bool = True,
    session_id: Optional[str] = None,
) -> str:
    """Full pipeline: analyze → save → update concepts → return feedback.

    This is the main entry point called after every interaction.
    Returns a brief outcome string (or empty if nothing notable).
    """
    store = get_store()

    # 1. Save problem record
    record = ProblemRecord(
        problem_text=problem,
        subject=subject,
        explanation=explanation,
        success=success,
        timestamp=__import__("time").time(),
        session_id=session_id,
    )
    store.save_problem(record)

    # 2. Run LLM analysis
    analysis = analyze_interaction(problem, explanation, subject, success)

    # 3. Update concepts
    for c in analysis.get("concepts", []):
        store.update_concept(
            name=c.get("name", "unknown"),
            level=c.get("level", 1),
            correct=success,
            notes=c.get("notes", ""),
        )

    # 4. Update preferences (low confidence, accumulates)
    for p in analysis.get("user_preferences", []):
        store.set_preference(
            key=p.get("key", "unknown"),
            value=p.get("value", ""),
            category="learning_style",
            confidence=0.4,  # starts low, increases with repeated observations
        )

    # 5. Return summary if anything interesting
    weak = store.weak_concepts(3)
    next_topics = analysis.get("next_topics", [])

    lines = []
    if next_topics:
        lines.append(f"💡 建议下一步学习: {', '.join(next_topics[:3])}")

    if weak:
        names = [c.name for c in weak]
        lines.append(f"⚠️  薄弱知识点: {', '.join(names[:3])}")

    return "\n".join(lines)


# ── Session management ─────────────────────────────────────────────────

def start_session(session_id: str) -> None:
    get_store().start_session(session_id)


def end_session(session_id: str) -> str:
    """End session and return a session summary."""
    # Get recent problems for summary
    store = get_store()

    # Try to have the LLM generate a summary from the session's problems
    problems = store.recent_problems(5)

    stats = store.stats()
    summary = f"Solved {stats['total_problems']} problems ({stats['success_rate']}% success)"

    store.end_session(session_id, summary)

    # Return a nice report
    return store.format_report()


# ── Suggest next steps ─────────────────────────────────────────────────

_NEXT_STEP_PROMPT = """\
Based on the user's learning profile below, suggest the NEXT STUDY TOPIC.

Profile:
{profile}

Current weak areas: {weak}
Mastered: {mastered}

Reply with a SHORT suggestion (1-3 sentences) of what to study next and why.
Be specific — name the concept and give a concrete starting point.
"""


def suggest_next_topic() -> str:
    """Suggest what the user should study next based on weak areas."""
    store = get_store()
    weak = store.weak_concepts(5)
    learned = store.learned_concepts(5)
    prefs = store.all_preferences()
    stats = store.stats()

    profile = store.format_report()
    weak_names = [c.name for c in weak]
    learned_names = [c.name for c in learned]

    if not weak:
        if stats["total_problems"] == 0:
            return "💡 还没有学习记录。随便问我一道题吧！"
        return "💡 目前没有发现薄弱环节！可以尝试新题型或更难的题目。"

    try:
        raw = _api_request(
            [
                {
                    "role": "system",
                    "content": _NEXT_STEP_PROMPT.format(
                        profile=profile[:800],
                        weak=", ".join(weak_names[:3]),
                        mastered=", ".join(learned_names[:3]) or "none yet",
                    ),
                },
                {
                    "role": "user",
                    "content": "What should I study next?",
                },
            ],
            max_tokens=256,
            temperature=0.5,
        )
        return f"📚 {raw.strip()}"
    except Exception as e:
        return f"💡 试试巩固一下: {', '.join(weak_names[:3])}"
