"""Run entry point for AI Study Buddy.

Usage:
    python -m study_buddy
"""

import logging
import sys

from study_buddy.bot import StudyBuddyBot
from study_buddy.config import config


def main() -> None:
    """Start the AI Study Buddy bot."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger = logging.getLogger("study_buddy")

    if not config.is_ready:
        logger.error(
            "Configuration incomplete. Set DEEPSEEK_API_KEY in your .env file."
        )
        sys.exit(1)

    bot = StudyBuddyBot()
    logger.info(
        "AI Study Buddy v0.1.0 initialized. "
        "Ready to process study problems."
    )

    # CLI interaction mode
    print("=" * 60)
    print("  AI Study Buddy - AI-Powered Study Assistant")
    print("  Type a problem or type 'exit' to quit.")
    print("=" * 60)

    while True:
        try:
            user_input = input("\n📝 You: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit", "q"):
                print("👋 Goodbye! Keep studying!")
                break

            response = bot.handle_text(user_input)
            print(f"\n🤖 Bot:\n{response}")

        except KeyboardInterrupt:
            print("\n👋 Goodbye! Keep studying!")
            break
        except Exception as e:
            logger.exception("Unexpected error")
            print(f"\n❌ Error: {e}")


if __name__ == "__main__":
    main()
