"""Core AI logic for AI Study Buddy.

Handles problem analysis via DeepSeek Vision API, step-by-step
explanations, and generation of similar practice problems.
"""

import base64
from typing import Any, Dict, List, Optional

import requests

from study_buddy.config import config


def _encode_image(image_path: str) -> str:
    """Read an image file and return its base64-encoded contents.

    Args:
        image_path: Path to the image file.

    Returns:
        Base64-encoded string of the image data.
    """
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _api_request(
    messages: List[Dict[str, Any]],
    max_tokens: int = 2048,
    temperature: float = 0.3,
) -> str:
    """Send a chat completion request to the API.

    Args:
        messages: List of message dicts for the chat completion.
        max_tokens: Maximum tokens in the response.
        temperature: Sampling temperature (lower = more deterministic).

    Returns:
        The text content of the assistant's reply.

    Raises:
        RuntimeError: If the API request fails or returns an error.
    """
    headers = {
        "Authorization": f"Bearer {config.deepseek_api_key}",
        "Content-Type": "application/json",
    }

    payload: Dict[str, Any] = {
        "model": config.model_name,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }

    try:
        response = requests.post(
            f"{config.deepseek_base_url.rstrip('/')}/chat/completions",
            headers=headers,
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]
    except requests.RequestException as e:
        raise RuntimeError(f"API request failed: {e}") from e
    except (KeyError, IndexError) as e:
        raise RuntimeError(f"Unexpected API response format: {e}") from e


def analyze_problem(image_path: str) -> Dict[str, str]:
    """Analyze a problem image using the Vision API.

    Sends the image to the model for OCR and problem understanding,
    returning the extracted problem text and detected subject.

    Args:
        image_path: Path to the problem image file.

    Returns:
        A dict with keys 'problem_text' and 'subject'.

    Raises:
        RuntimeError: If the image cannot be processed.
        FileNotFoundError: If the image file does not exist.
    """
    import os
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image file not found: {image_path}")

    image_data = _encode_image(image_path)

    messages = [
        {
            "role": "system",
            "content": (
                "You are an AI study assistant. Analyze the image of a problem. "
                "Extract the text of the problem and identify its subject. "
                "Respond with:\n"
                "Subject: <subject>\n"
                "Problem: <problem text>"
            ),
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{image_data}",
                    },
                },
            ],
        },
    ]

    response = _api_request(messages, max_tokens=1024, temperature=0.1)

    # Parse subject and problem text from response
    subject = "general"
    problem_text = response

    for line in response.split("\n"):
        line = line.strip()
        if line.lower().startswith("subject:"):
            subject = line.split(":", 1)[1].strip()
        elif line.lower().startswith("problem:"):
            problem_text = line.split(":", 1)[1].strip()

    return {
        "problem_text": problem_text,
        "subject": subject,
    }


def explain_step_by_step(problem_text: str) -> str:
    """Generate a structured step-by-step explanation for a problem.

    Args:
        problem_text: The text of the problem to explain.

    Returns:
        A formatted string with the step-by-step explanation.
    """
    messages = [
        {
            "role": "system",
            "content": (
                "You are a patient and thorough tutor. Explain the solution "
                "to the given problem step by step. Use clear, numbered steps. "
                "Include the final answer at the end. Be detailed but "
                "easy to follow."
            ),
        },
        {
            "role": "user",
            "content": f"Explain this problem step by step:\n\n{problem_text}",
        },
    ]

    return _api_request(messages, max_tokens=2048, temperature=0.3)


def generate_similar_problems(
    problem_text: str,
    count: int = 3,
) -> List[Dict[str, str]]:
    """Generate similar practice problems with answers.

    Args:
        problem_text: The original problem text to base new problems on.
        count: Number of similar problems to generate.

    Returns:
        A list of dicts with 'problem' and 'answer' keys.
    """
    messages = [
        {
            "role": "system",
            "content": (
                "You are a tutor creating practice problems. Based on the "
                "given problem, generate {count} similar but distinct "
                "problems of the same type and difficulty. Provide the "
                "answer for each. Format each as:\n"
                "Problem 1: ...\nAnswer 1: ...\n"
                "Problem 2: ...\nAnswer 2: ..."
            ).format(count=count),
        },
        {
            "role": "user",
            "content": (
                f"Original problem:\n{problem_text}\n\n"
                f"Generate {count} similar problems with answers."
            ),
        },
    ]

    response = _api_request(messages, max_tokens=2048, temperature=0.7)

    # Parse response into structured list
    problems: List[Dict[str, str]] = []
    current_problem: Optional[str] = None
    current_answer: Optional[str] = None

    for line in response.split("\n"):
        line = line.strip()
        if not line:
            continue

        lower = line.lower()

        if lower.startswith("problem"):
            # Save previous entry if exists
            if current_problem is not None:
                problems.append({
                    "problem": current_problem,
                    "answer": current_answer or "",
                })
            # Extract problem text after "Problem N:"
            parts = line.split(":", 1)
            current_problem = parts[1].strip() if len(parts) > 1 else ""
            current_answer = None

        elif lower.startswith("answer"):
            parts = line.split(":", 1)
            current_answer = parts[1].strip() if len(parts) > 1 else ""

    # Save the last entry
    if current_problem is not None:
        problems.append({
            "problem": current_problem,
            "answer": current_answer or "",
        })

    return problems
