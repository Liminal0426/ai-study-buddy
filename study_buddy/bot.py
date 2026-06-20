"""WeChat/Telegram bot handler for AI Study Buddy.

Receives messages (images and text), routes them to the solver,
and returns explanations along with practice problems.
"""

import logging
from typing import Any, Dict, Optional

from study_buddy.config import config
from study_buddy.db import init_db, save_problem
from study_buddy.solver import (
    analyze_problem,
    explain_step_by_step,
    generate_similar_problems,
)

logger = logging.getLogger(__name__)


class StudyBuddyBot:
    """Main bot class for handling incoming study-related messages.

    Handles image-based problem submissions and text queries,
    delegating to the solver module and returning formatted responses.
    """

    def __init__(self) -> None:
        self.name = "AI Study Buddy"
        init_db()

    def handle_image(self, image_path: str) -> str:
        """Handle an image message containing a problem.

        Analyzes the image, generates an explanation, and creates
        similar practice problems.

        Args:
            image_path: Path to the received image file.

        Returns:
            A formatted response string with analysis, explanation,
            and practice problems.
        """
        try:
            # Step 1: Extract problem from image
            analysis = analyze_problem(image_path)
            problem_text = analysis["problem_text"]
            subject = analysis["subject"]

            # Step 2: Save to database
            problem_id = save_problem(problem_text, subject)

            # Step 3: Generate explanation
            explanation = explain_step_by_step(problem_text)

            # Step 4: Generate similar problems
            similar = generate_similar_problems(problem_text)

            # Step 5: Build response
            response_lines = [
                f"📐 **Analysis:**",
                f"Subject: {subject}",
                f"Problem: {problem_text}",
                "",
                explanation,
                "",
                "🎯 **Practice Problems:**",
            ]

            for i, sp in enumerate(similar, 1):
                response_lines.append(f"{i}. {sp['problem']}")
                response_lines.append(f"   → {sp['answer']}")

            return "\n".join(response_lines)

        except Exception as e:
            logger.exception("Failed to process image")
            return f"❌ Sorry, I couldn't process that image. Error: {e}"

    def handle_text(self, text: str) -> str:
        """Handle a text message containing a problem or question.

        Args:
            text: The user's text message.

        Returns:
            A formatted response with the explanation.
        """
        try:
            # Save to database
            problem_id = save_problem(text)

            # Generate explanation
            explanation = explain_step_by_step(text)

            # Generate similar problems
            similar = generate_similar_problems(text)

            response_lines = [
                explanation,
                "",
                "🎯 **Practice Problems:**",
            ]

            for i, sp in enumerate(similar, 1):
                response_lines.append(f"{i}. {sp['problem']}")
                response_lines.append(f"   → {sp['answer']}")

            return "\n".join(response_lines)

        except Exception as e:
            logger.exception("Failed to process text")
            return f"❌ Sorry, I couldn't process that. Error: {e}"

    def handle_message(
        self,
        message_type: str,
        content: str,
    ) -> str:
        """Route an incoming message to the appropriate handler.

        Args:
            message_type: Either 'image' or 'text'.
            content: Path to image file (for 'image') or text content.

        Returns:
            The bot's response string.
        """
        if message_type == "image":
            return self.handle_image(content)
        elif message_type == "text":
            return self.handle_text(content)
        else:
            return f"❌ Unsupported message type: {message_type}"
