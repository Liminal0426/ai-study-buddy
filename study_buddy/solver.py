"""Core AI logic for AI Study Buddy.

Multi-provider solver with vision support and geometry drawing
instruction generation.
"""
from __future__ import annotations

import base64
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple

import requests

from study_buddy.config import config
from study_buddy.drawer import render_geometry

logger = logging.getLogger(__name__)


# ── Vision provider fallback ──────────────────────────────────────────
# DeepSeek marks deepseek-chat as vision=True but the API rejects images.
# These providers actually support vision based on confirmed API tests.

_VISION_PROVIDERS = {
    "zhipuai": {"model": "glm-4v-plus", "vision": True},       # confirmed
    "openai": {"model": "gpt-4o", "vision": True},             # confirmed
    "anthropic": {"model": "claude-sonnet-4-20250514", "vision": True},  # confirmed
    "google": {"model": "gemini-2.0-flash", "vision": True},   # confirmed
    "qwen": {"model": "qwen-vl-plus", "vision": True},     # confirmed
    "moonshot": {"model": "moonshot-v1-8k", "vision": True},  # presumed
    "mistral": {"model": "mistral-large-latest", "vision": True},  # presumed
}


def _find_vision_provider() -> Optional[Tuple[str, str]]:
    """Find an available provider that actually supports vision.

    Returns (provider_name, model_name) or None.
    """
    for pname, info in _VISION_PROVIDERS.items():
        prov = config.available_providers.get(pname)
        if prov and prov.get("api_key"):
            return (pname, info["model"])
    return None


def _vision_api_request(
    messages: List[Dict[str, Any]],
    max_tokens: int = 4096,
    temperature: float = 0.1,
) -> str:
    """Send a vision request using a vision-capable provider.

    Falls back to the active provider's _api_request if no vision
    provider is available (will likely fail for image requests).
    """
    vision = _find_vision_provider()
    if not vision:
        # No vision provider — try default (will fail for images)
        logger.warning("No vision-capable provider found, using default")
        return _api_request(messages, max_tokens, temperature)

    pname, model = vision
    prov = config.available_providers[pname]
    api_key = prov["api_key"]
    base_url = prov["base_url"].rstrip("/")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }

    # ── Anthropic format ──
    if pname == "anthropic":
        return _anthropic_request(api_key, base_url, model, messages, max_tokens, temperature)

    # ── Google Gemini format ──
    if pname == "google":
        return _gemini_request(api_key, base_url, model, messages, max_tokens, temperature)

    # ── OpenAI-compatible ──
    try:
        resp = requests.post(
            f"{base_url}/chat/completions",
            headers=headers,
            json=payload,
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except requests.RequestException as e:
        raise RuntimeError(f"[{pname}] Vision API request failed: {e}") from e
    except (KeyError, IndexError) as e:
        raise RuntimeError(f"[{pname}] Unexpected response format: {e}") from e


# ── Public API ────────────────────────────────────────────────────────


def classify_intent(user_input: str) -> str:
    """Cheap classification: does this request need a photo or geometry?

    Returns one of: 'photo', 'geometry', 'solve'
    """
    messages = [
        {
            "role": "system",
            "content": (
                "Classify the user's intent. Reply with EXACTLY one word.\n\n"
                "- photo    — user explicitly wants to USE THE CAMERA / take a photo / snap a picture.\n"
        "             Triggers: 拍照, 拍个照, 照一下, 拍张照, 用相机, take a picture, snap, camera.\n"
        "             DOES NOT include: 看, 看看, 帮我看看, 看一下, 写, 读, 如图, 如图所示 (these are solve).\n\n"
        "- geometry — user wants to DRAW A GRAPH / plot a function / draw a diagram.\n"
        "             Triggers: 画图, 画函数, 画图像, 画一下, draw, plot, graph of, diagram.\n"
        "             DOES NOT include: 三角函数 (solve — topic study), 学, 背, 记, 公式 (text study).\n"
        "             A standalone word 函数 without 画/plot is solve, not geometry.\n\n"
        "- solve    — everything else: homework help, step-by-step, explain, study.\n\n"
        "Examples:\n"
        "  '帮我看这道题' → solve  (not photo — user wants help, not camera)\n"
        "  '拍个照然后帮我解题' → photo\n"
        "  '画y=x²' → geometry\n"
        "  'x²+2x+1=0' → solve\n"
        "  '勾股定理' → solve\n"
        "  '三角函数' → solve\n"
        "  '帮我看看这个' → solve  (看看 = look, not photo)\n"
        "  '用相机照一下这道题' → photo\n\n"
                "Only reply with the single word. No punctuation."
            ),
        },
        {"role": "user", "content": user_input},
    ]
    try:
        raw = _api_request(messages, max_tokens=8, temperature=0.0)
        raw = raw.strip().lower().rstrip(".")
        if raw in ("photo", "geometry"):
            return raw
        return "solve"
    except Exception:
        return "solve"


def analyze_problem(image_path: str) -> Dict[str, str]:
    """Analyze a problem image via the active vision-capable provider.

    Returns {"problem_text": ..., "subject": ..., "draw_instructions": ...}
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image file not found: {image_path}")

    image_data = _encode_image(image_path)

    system_msg = (
        "You are an AI study assistant specialised in STEM problems.  "
        "Analyse the image.  Extract the exact problem text and identify the subject.  "
        "If the problem involves GEOMETRY or GRAPHING (functions, circles, "
        "coordinate axes, number lines, triangles in plane), also output a JSON "
        "drawing instruction block at the end inside <<<DRAW>>> ... <<<DRAW>>> markers.\n\n"
        "Respond with:\n"
        "Subject: <subject>\n"
        "Problem: <problem text>\n"
        "<<<DRAW>>>\n"
        '{\n  "title": "...",\n  "elements": [...]\n}\n'
        "<<<DRAW>>>\n\n"
        "If no drawing is needed, omit the DRAW block entirely."
    )

    messages = [
        {"role": "system", "content": system_msg},
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}},
            ],
        },
    ]

    raw = _vision_api_request(messages, max_tokens=4096, temperature=0.1)
    return _parse_analysis(raw)


def explain_step_by_step(problem_text: str, is_geometry: bool = False) -> str:
    """Generate a structured step-by-step explanation."""
    sys = (
        "You are a patient, thorough STEM tutor.  Explain the solution "
        "step by step with numbered steps.  Include the final answer.  "
        "Be detailed but clear.  Use LaTeX for math expressions ($$...$$)."
    )
    if is_geometry:
        sys += (
            "\n\n"
            "GEOMETRY DRAWING INSTRUCTION - YOU MUST FOLLOW THIS EXACTLY:\n"
            "At the END of your explanation, add a code block with these EXACT markers:\n"
            "<<<DRAW>>>\n"
            '{"title": "函数 y = x^2 与 y = x + 2", "x_range": [-5, 5], "y_range": [-5, 10], '
            '"elements": [{"type": "function", "expr": "x**2", "label": "y = x^2", "color": "blue"}, '
            '{"type": "function", "expr": "x + 2", "label": "y = x + 2", "color": "red"}]}\n'
            "<<<DRAW>>>\n"
            "Replace the JSON above with actual equations from THIS problem. "
            "Valid element types: function (expr in Python, e.g. 2*x+1, x**2-4), "
            "circle (center, radius), point (x, y), number_line (min, max, ticks), "
            "segment (x1,y1,x2,y2).  ALWAYS include <<<DRAW>>> markers when the problem "
            "involves graphs, functions, or geometry."
        )

    messages = [
        {"role": "system", "content": sys},
        {"role": "user", "content": f"Explain this problem step by step:\n\n{problem_text}"},
    ]

    return _api_request(messages, max_tokens=4096, temperature=0.3)


def generate_similar_problems(problem_text: str, count: int = 3) -> List[Dict[str, str]]:
    """Generate similar practice problems with answers."""
    messages = [
        {
            "role": "system",
            "content": (
                "You are a tutor creating practice problems.  Based on the given problem, "
                f"generate {count} similar but distinct problems of the same type and difficulty. "
                "Provide the answer for each.  Format as:\n"
                "Problem 1: ...\nAnswer 1: ...\n"
                "Problem 2: ...\nAnswer 2: ..."
            ),
        },
        {
            "role": "user",
            "content": f"Original problem:\n{problem_text}\n\nGenerate {count} similar problems with answers.",
        },
    ]

    resp = _api_request(messages, max_tokens=4096, temperature=0.7)
    return _parse_problems(resp)


def solve_geometry(problem_input: str, image_path: Optional[str] = None) -> Dict[str, Any]:
    """Full geometry pipeline: analyse → explain → draw.

    Returns {"explanation": str, "diagram_path": str|None, "subject": str}
    """
    if image_path:
        analysis = analyze_problem(image_path)
    else:
        analysis = {"problem_text": problem_input, "subject": "geometry", "draw_instructions": None}
        # Have the AI extract a clean problem statement (not the user's command)
        try:
            _extracted = _extract_problem_text(problem_input)
            if _extracted:
                analysis["problem_text"] = _extracted
        except Exception:
            pass

    problem_text = analysis["problem_text"]
    subject = analysis["subject"]

    # Get explanation
    explanation = explain_step_by_step(problem_text, is_geometry=True)

    # Try to extract DRAW block from explanation
    draw_json = _extract_draw_block(explanation)
    if not draw_json and analysis.get("draw_instructions"):
        draw_json = analysis["draw_instructions"]

    # If still no drawing instructions, ask the AI specifically for them
    if not draw_json:
        draw_json = _generate_drawing_json(problem_text)

    diagram_path = None
    if draw_json:
        try:
            diagram_path = render_geometry(draw_json)
        except Exception as e:
            logger.warning("Failed to render diagram: %s", e)
            diagram_path = None

    # Clean draw block from explanation for display
    clean_explanation = re.sub(
        r"<<<DRAW>>>.*?<<<DRAW>>>", "", explanation, flags=re.DOTALL
    ).strip()

    return {
        "explanation": clean_explanation,
        "diagram_path": diagram_path,
        "subject": subject,
        "problem_text": problem_text,
    }


def _generate_drawing_json(problem_text: str) -> Optional[Dict[str, Any]]:
    """Ask the AI specifically to produce drawing JSON (no explanation)."""
    messages = [
        {
            "role": "system",
            "content": (
                "You are a math diagram generator.  Given a math problem involving "
                "functions, geometry, or graphs, output ONLY a JSON object for rendering.  "
                "NO explanation, NO markdown, NO commentary — just valid JSON.\n\n"
                "The JSON format:\n"
                '{"title": "...", "x_range": [-5, 5], "y_range": [-5, 5], '
                '"elements": [\n'
                '  {"type": "function", "expr": "2*x + 1", "label": "y = 2x + 1", "color": "blue"},\n'
                '  {"type": "function", "expr": "x**2 - 4", "label": "y = x² - 4", "color": "red"},\n'
                '  {"type": "point", "x": 0, "y": 1, "label": "(0,1)", "color": "green"},\n'
                '  {"type": "circle", "center": [0, 0], "radius": 3, "label": "x²+y²=9", "color": "purple"},\n'
                '  {"type": "number_line", "min": -5, "max": 5, '
                '"ticks": [-5, -4, -3, -2, -1, 0, 1, 2, 3, 4, 5], '
                '"highlight": [0], "color": "blue"},\n'
                '  {"type": "angle", "vertex": [4, 0], "ray1": [0, 0], "ray2": [1, 3], '
                '"label": "60°", "color": "red", "arc_radius": 0.6},\n'
                ']\n\n'
                "IMPORTANT:\n"
                "- Use Python math syntax: x**2 (not x^2), 2*x + 1\n"
                "- Set reasonable x_range/y_range to show all elements\n"
                "- Include ALL relevant functions, points, and shapes\n"
                "- For equations that aren't explicit functions, solve for y first\n"
                "- ONLY return the JSON, nothing else"
            ),
        },
        {"role": "user", "content": f"Generate drawing JSON for: {problem_text}"},
    ]

    try:
        raw = _api_request(messages, max_tokens=2048, temperature=0.1)
        # Strip any markdown code fences
        raw = re.sub(r"```json\s*", "", raw)
        raw = re.sub(r"```\s*", "", raw)
        raw = raw.strip()
        return json.loads(raw)
    except Exception as e:
        logger.warning("Failed to generate drawing JSON: %s", e)
        return None


# ── API Request (multi-provider) ──────────────────────────────────────


def _api_request(
    messages: List[Dict[str, Any]],
    max_tokens: int = 2048,
    temperature: float = 0.3,
    model: Optional[str] = None,
) -> str:
    """Send a chat-completion request to the active provider.

    Args:
        model: Override the active model (e.g. use vision model for images).
    """
    provider = config.get_provider()
    if not provider:
        raise RuntimeError("No provider with a valid API key configured. "
                           f"Available: {[p for p in config.available_providers]}")

    active_model = model or config.active_model
    base_url = provider["base_url"].rstrip("/")
    api_key = provider["api_key"]

    provider_name = config.active_provider

    # ── Anthropic uses its own format ──
    if provider_name == "anthropic":
        return _anthropic_request(api_key, base_url, active_model, messages, max_tokens, temperature)

    # ── Google Gemini uses its own format ──
    if provider_name == "google":
        return _gemini_request(api_key, base_url, active_model, messages, max_tokens, temperature)

    # ── OpenAI-compatible (DeepSeek, ZhipuAI, Qwen, Moonshot, Mistral, etc.) ──
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload: Dict[str, Any] = {
        "model": active_model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }

    try:
        resp = requests.post(
            f"{base_url}/chat/completions",
            headers=headers,
            json=payload,
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except requests.RequestException as e:
        raise RuntimeError(f"[{provider_name}] API request failed: {e}") from e
    except (KeyError, IndexError) as e:
        raise RuntimeError(f"[{provider_name}] Unexpected response format: {e}") from e


def _anthropic_request(
    api_key: str, base_url: str, model: str,
    messages: List[Dict[str, Any]], max_tokens: int, temperature: float,
) -> str:
    """Anthropic-specific API call."""
    # Convert OpenAI-style messages to Anthropic format
    system = ""
    converted = []
    for msg in messages:
        role = msg["role"]
        content = msg["content"]
        if role == "system":
            system = content if isinstance(content, str) else str(content)
            continue
        if isinstance(content, list):
            # Image content
            anth_content = []
            for part in content:
                if part.get("type") == "image_url":
                    url = part["image_url"]["url"]
                    if url.startswith("data:"):
                        _, b64data = url.split(",", 1)
                        media_type = url.split(";")[0].split(":")[1]
                        anth_content.append({
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": b64data,
                            },
                        })
                    else:
                        anth_content.append({"type": "text", "text": f"[Image: {url}]"})
                elif part.get("type") == "text":
                    anth_content.append({"type": "text", "text": part["text"]})
            converted.append({"role": "user", "content": anth_content})
        else:
            converted.append({"role": role, "content": str(content)})

    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": converted,
    }
    if system:
        payload["system"] = system

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    try:
        resp = requests.post(
            f"{base_url}/messages",
            headers=headers,
            json=payload,
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["content"][0]["text"]
    except requests.RequestException as e:
        raise RuntimeError(f"[anthropic] API request failed: {e}") from e


def _gemini_request(
    api_key: str, base_url: str, model: str,
    messages: List[Dict[str, Any]], max_tokens: int, temperature: float,
) -> str:
    """Google Gemini-specific API call."""
    # Convert to Gemini format
    gemini_contents = []
    system = ""

    for msg in messages:
        role = msg["role"]
        content = msg["content"]
        if role == "system":
            system = content if isinstance(content, str) else str(content)
            continue

        parts = []
        if isinstance(content, list):
            for part in content:
                if part.get("type") == "image_url":
                    url = part["image_url"]["url"]
                    if url.startswith("data:"):
                        _, b64 = url.split(",", 1)
                        parts.append({
                            "inline_data": {
                                "mime_type": "image/jpeg",
                                "data": b64,
                            }
                        })
                    else:
                        parts.append({"text": f"[Image: {url}]"})
                elif part.get("type") == "text":
                    parts.append({"text": part["text"]})
        else:
            parts.append({"text": str(content)})

        gemini_role = "model" if role == "assistant" else "user"
        gemini_contents.append({"role": gemini_role, "parts": parts})

    payload: Dict[str, Any] = {
        "contents": gemini_contents,
        "generationConfig": {
            "maxOutputTokens": max_tokens,
            "temperature": temperature,
        },
    }
    if system:
        payload["systemInstruction"] = {"parts": [{"text": system}]}

    try:
        resp = requests.post(
            f"{base_url}/models/{model}:generateContent?key={api_key}",
            json=payload,
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except requests.RequestException as e:
        raise RuntimeError(f"[google] API request failed: {e}") from e


# ── Helpers ───────────────────────────────────────────────────────────


def _encode_image(image_path: str) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _parse_analysis(raw: str) -> Dict[str, str]:
    subject = "general"
    problem_text = raw
    draw_instructions = None

    lines = raw.split("\n")
    for i, line in enumerate(lines):
        ls = line.strip().lower()
        if ls.startswith("subject:"):
            subject = line.split(":", 1)[1].strip()
        elif ls.startswith("problem:"):
            problem_text = line.split(":", 1)[1].strip()

    draw_match = re.search(r"<<<DRAW>>>\s*(.*?)\s*<<<DRAW>>>", raw, re.DOTALL)
    if draw_match:
        try:
            draw_instructions = json.loads(draw_match.group(1))
        except json.JSONDecodeError:
            draw_instructions = None

    return {
        "problem_text": problem_text,
        "subject": subject,
        "draw_instructions": draw_instructions,
    }


def _extract_draw_block(text: str) -> Optional[Dict[str, Any]]:
    match = re.search(r"<<<DRAW>>>\s*(.*?)\s*<<<DRAW>>>", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            return None
    return None


_PROBLEM_EXTRACT_PROMPT = """\
Given a user's request, extract ONLY the actual math problem statement.
Remove any commands like "画", "画图", "draw", "plot", "solve", etc.

Examples:
  Input: "画y=x²-4的图像"
  Output: "绘制函数 y = x² - 4 的图像"

  Input: "画一下y=2x+1的函数图像"
  Output: "绘制函数 y = 2x + 1 的图像"

  Input: "帮我解这个方程 3x+5=20"
  Output: "3x + 5 = 20"

Output ONLY the problem statement. No explanation, no commentary.
"""


def _extract_problem_text(user_input: str) -> str:
    """Use LLM to extract a clean problem statement from user input."""
    messages = [
        {"role": "system", "content": _PROBLEM_EXTRACT_PROMPT},
        {"role": "user", "content": user_input},
    ]
    return _api_request(messages, max_tokens=128, temperature=0.0).strip()


def _parse_problems(response: str) -> List[Dict[str, str]]:
    problems: List[Dict[str, str]] = []
    current_problem: Optional[str] = None
    current_answer: Optional[str] = None

    for line in response.split("\n"):
        line = line.strip()
        if not line:
            continue
        lower = line.lower()

        if lower.startswith("problem"):
            if current_problem is not None:
                problems.append({"problem": current_problem, "answer": current_answer or ""})
            parts = line.split(":", 1)
            current_problem = parts[1].strip() if len(parts) > 1 else ""
            current_answer = None
        elif lower.startswith("answer"):
            parts = line.split(":", 1)
            current_answer = parts[1].strip() if len(parts) > 1 else ""

    if current_problem is not None:
        problems.append({"problem": current_problem, "answer": current_answer or ""})

    return problems
