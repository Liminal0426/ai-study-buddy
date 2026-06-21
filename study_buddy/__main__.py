"""CLI entry point for AI Study Buddy.

Usage:
    python -m study_buddy

Just type naturally — the AI figures out what to do:
    "帮我看这道题"       → takes photo → analyzes
    "x² + 2x + 1 = 0"  → solves step by step
    "画y=x²的函数图像"   → draws geometry diagram
    "我的学习报告"       → shows your learning stats & progress
    "下一步学什么"       → AI suggests what to study next
    exit / quit / q     — exit
"""
from __future__ import annotations

import logging
import sys
import uuid

from study_buddy.bot import StudyBuddyBot
from study_buddy.config import config
from study_buddy.evolution import end_session

logger = logging.getLogger(__name__)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if not config.is_ready:
        logger.error(
            "No provider configured.  Set at least one API key in .env:\n"
            "  DEEPSEEK_API_KEY=sk-...\n"
            "  OPENAI_API_KEY=sk-...\n"
            "  ZHIPUAI_API_KEY=...\n"
            "  etc."
        )
        sys.exit(1)

    # Session ID for memory tracking
    session_id = uuid.uuid4().hex[:12]
    bot = StudyBuddyBot(session_id=session_id)

    logger.info(
        "AI Study Buddy v0.2.0 initialized.  "
        "Active: %s / %s  Session: %s",
        config.active_provider,
        config.active_model,
        session_id,
    )

    print("=" * 60)
    print("  AI Study Buddy v0.2.0")
    print(f"  Active: {config.get_provider()['label']} / {config.active_model}")
    print("  Just type naturally — the AI figures out what to do.")
    print("  Try: '我的学习报告'  '下一步学什么'")
    print("  Type 'exit' to quit.")
    print("=" * 60)

    prompt = "\n📝 You: "

    while True:
        try:
            user_input = input(prompt).strip()
        except EOFError:
            print()
            break
        except KeyboardInterrupt:
            print("\n\n👋 Goodbye! Keep studying!")
            _show_goodbye(bot, session_id)
            break

        if not user_input:
            continue

        if user_input.lower() in ("exit", "quit", "q"):
            print("👋 Goodbye! Keep studying!")
            _show_goodbye(bot, session_id)
            break

        try:
            response = bot.handle_any(user_input)
            print(f"\n🤖 Bot:\n{response}")
        except Exception as e:
            logger.exception("Unexpected error")
            print(f"\n❌ Error: {e}")


def _show_goodbye(bot: StudyBuddyBot, session_id: str) -> None:
    """Show session summary on exit."""
    try:
        report = end_session(session_id)
        print(f"\n📊 Session Summary:\n{report}")
    except Exception as e:
        logger.debug("Could not generate session summary: %s", e)


if __name__ == "__main__":
    main()
