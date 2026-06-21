"""Bot handler for AI Study Buddy.

Routes messages (text / image) to the solver and optionally
renders geometry diagrams. Integrates memory + self-evolution.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from study_buddy.config import config
from study_buddy.db import init_db, save_problem
from study_buddy.drawer import render_geometry
from study_buddy.evolution import (
    end_session,
    process_interaction,
    start_session,
    suggest_next_topic,
)
from study_buddy.exporter import export_all
from study_buddy.memory import get_store
from study_buddy.platform import is_windows, pick_image, take_photo
from study_buddy.solver import (
    analyze_problem,
    classify_intent,
    explain_step_by_step,
    generate_similar_problems,
    solve_geometry,
)

logger = logging.getLogger(__name__)


class StudyBuddyBot:
    """Main bot class with memory + self-evolution."""

    def __init__(self, session_id: Optional[str] = None) -> None:
        self.name = "AI Study Buddy"
        init_db()
        self.session_id = session_id or "default"
        start_session(self.session_id)
        self._last_subject: Optional[str] = None

    # ── Smart router (no commands needed) ───────────────────────────────

    def handle_any(self, text: str) -> str:
        """Route user input to the right handler, then run self-evolution."""

        # Special keywords that trigger reports instead of solving
        text_lower = text.strip().lower()
        if text_lower in ("报告", "我的学习报告", "学习报告", "进度", "report", "stats"):
            return get_store().format_report()

        if text_lower in ("下一步学什么", "推荐", "建议", "next", "suggest", "recommend"):
            return suggest_next_topic()

        intent = classify_intent(text)

        if intent == "photo":
            response = self._snap_and_analyze()
        elif intent == "geometry":
            response = self.handle_geometry(text)
        else:
            response = self.handle_text(text)

        # Self-evolution: learn from this interaction (background)
        self._learn_from(text, response)

        return response

    def _learn_from(self, user_input: str, bot_response: str) -> None:
        """After each turn, extract concepts and update memory."""
        try:
            # Extract problem text and subject from the response
            subject = self._last_subject or "general"
            result = process_interaction(
                problem=user_input[:500],
                explanation=bot_response[:800],
                subject=subject,
                success=True,
                session_id=self.session_id,
            )
            if result:
                logger.debug("Self-evolution: %s", result)
        except Exception as e:
            logger.debug("Self-evolution skipped: %s", e)

    def _snap_and_analyze(self) -> str:
        """Take a photo or pick from storage (platform-appropriate)."""
        if is_windows():
            # Windows: file picker dialog
            ok, path = pick_image()
            if not ok:
                return f"❌ {path}"
            return self.handle_image(path)

        # Android: ask user which method
        import sys
        print("\n📸 选择来源:")
        print("   1. 拍照")
        print("   2. 从相册/文件选")
        choice = input("   Enter 1 or 2: ").strip()

        import tempfile, os, subprocess
        tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        tmp.close()
        try:
            if choice == "2":
                # File picker via termux-storage-get
                print("   📂 请在手机上选择图片...")
                r = subprocess.run(
                    ["termux-storage-get", tmp.name],
                    capture_output=True, text=True, timeout=30,
                )
                if r.returncode != 0:
                    return f"❌ 没有选择文件: {r.stderr.strip() or r.stdout.strip()}"
                return self.handle_image(tmp.name)
            else:
                # Camera
                print("   📸 拍照中...")
                ok, result = take_photo(tmp.name)
                if not ok:
                    return f"❌ 拍照失败: {result}"
                return self.handle_image(tmp.name)
        except FileNotFoundError:
            return "❌ termux-api not installed. Run: pkg install termux-api"
        except subprocess.TimeoutExpired:
            return "❌ 操作超时"
        except Exception as e:
            return f"❌ 出错: {e}"
        finally:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass

    # ── Public handlers ───────────────────────────────────────────────

    def handle_image(self, image_path: str) -> str:
        try:
            analysis = analyze_problem(image_path)
            problem_text = analysis["problem_text"]
            subject = analysis["subject"]
            self._last_subject = subject

            if analysis.get("draw_instructions"):
                return self._geometry_response(
                    problem_text, analysis["draw_instructions"], image_path
                )

            problem_id = save_problem(problem_text, subject)
            explanation = explain_step_by_step(problem_text)
            similar = generate_similar_problems(problem_text)

            return self._format_response(subject, problem_text, explanation, similar)
        except Exception as e:
            logger.exception("Failed to process image")
            return f"❌ Could not process image. Error: {e}"

    def handle_text(self, text: str) -> str:
        try:
            if text.startswith("/export "):
                return self.handle_export(text[len("/export "):].strip())

            is_geo = _is_geometry_problem(text)

            if is_geo:
                return self._handle_geo_text(text)

            problem_id = save_problem(text)
            explanation = explain_step_by_step(text)
            similar = generate_similar_problems(text)
            self._last_subject = "general"

            lines = [explanation, "", "🎯 **Practice Problems:**"]
            for i, sp in enumerate(similar, 1):
                lines.append(f"{i}. {sp['problem']}")
                lines.append(f"   → {sp['answer']}")
            return "\n".join(lines)
        except Exception as e:
            logger.exception("Failed to process text")
            return f"❌ Could not process. Error: {e}"

    def _handle_geo_text(self, text: str) -> str:
        result = solve_geometry(text)
        self._last_subject = result.get("subject", "geometry")
        problem_text = result.get("problem_text", text)
        lines = [
            f"📐 **Subject:** {result['subject']}",
            "",
            result["explanation"],
        ]
        if result["diagram_path"]:
            lines.append("")
            lines.append(f"📊 **Diagram saved:** `{result['diagram_path']}`")
            exports = export_all(
                title=text[:50],
                problem_text=problem_text,
                explanation=result["explanation"],
                diagram_path=result["diagram_path"],
            )
            lines.append("")
            lines.append("📦 **Exported:**")
            for fmt, path in exports.items():
                lines.append(f"   {fmt}: `{path}`")
        return "\n".join(lines)

    def handle_export(self, text: str) -> str:
        """Export a problem explanation + diagram as TXT, PDF, Word."""
        result = solve_geometry(text)
        exports = export_all(
            title=text[:50],
            problem_text=text,
            explanation=result["explanation"],
            diagram_path=result["diagram_path"],
        )
        lines = [
            f"📐 **Subject:** {result['subject']}",
            "",
            result["explanation"],
        ]
        if result["diagram_path"]:
            lines.append("")
            lines.append(f"📊 **Diagram:** `{result['diagram_path']}`")
        lines.append("")
        lines.append("📦 **Exported files:**")
        for fmt, path in exports.items():
            lines.append(f"   {fmt}: `{path}`")
        return "\n".join(lines)

    def handle_message(self, message_type: str, content: str) -> str:
        if message_type == "image":
            return self.handle_image(content)
        elif message_type == "text":
            return self.handle_text(content)
        else:
            return f"❌ Unsupported message type: {message_type}"

    def handle_geometry(self, text: str) -> str:
        """Dedicated geometry handler with export."""
        result = solve_geometry(text)
        self._last_subject = result.get("subject", "geometry")
        problem_text = result.get("problem_text", text)
        lines = [
            f"📐 **Subject:** {result['subject']}",
            "",
            result["explanation"],
        ]
        if result["diagram_path"]:
            lines.append("")
            lines.append(f"📊 **Diagram:** `{result['diagram_path']}`")
            exports = export_all(
                title=text[:50],
                problem_text=problem_text,
                explanation=result["explanation"],
                diagram_path=result["diagram_path"],
            )
            lines.append("")
            lines.append("📦 **Exported:**")
            for fmt, path in exports.items():
                lines.append(f"   {fmt}: `{path}`")
        return "\n".join(lines)

    def list_providers(self) -> str:
        providers = config.list_providers()
        if not providers:
            return "❌ No providers configured. Set API keys in .env"
        lines = ["Available providers:"]
        for p in providers:
            marker = "→" if p["name"] == config.active_provider else " "
            lines.append(f"  {marker} {p['label']} ({p['name']})")
            for m in p["models"]:
                active = " ◀" if m == config.active_model else ""
                lines.append(f"      - {m}{active}")
        return "\n".join(lines)

    def switch_provider(self, provider_name: str, model_name: Optional[str] = None) -> str:
        return config.switch_provider(provider_name, model_name)

    # ── Internal ──────────────────────────────────────────────────────

    def _geometry_response(
        self,
        problem_text: str,
        draw_instructions: Dict[str, Any],
        image_path: str,
    ) -> str:
        result = solve_geometry(problem_text, image_path)
        self._last_subject = result.get("subject", "geometry")
        lines = [
            f"📐 **Subject:** {result['subject']}",
            "",
            result["explanation"],
        ]
        if result["diagram_path"]:
            lines.append("")
            lines.append(f"📊 **Diagram saved:** `{result['diagram_path']}`")
        return "\n".join(lines)

    @staticmethod
    def _format_response(
        subject: str,
        problem_text: str,
        explanation: str,
        similar: list,
    ) -> str:
        lines = [
            f"📐 **Subject:** {subject}",
            f"**Problem:** {problem_text}",
            "",
            explanation,
            "",
            "🎯 **Practice Problems:**",
        ]
        for i, sp in enumerate(similar, 1):
            lines.append(f"{i}. {sp['problem']}")
            lines.append(f"   → {sp['answer']}")
        return "\n".join(lines)


# ── Geometry detection ────────────────────────────────────────────────

_GEO_KEYWORDS = {
    "geometry", "几何", "graph", "function", "函数",
    "circle", "圆", "triangle", "三角", "angle", "角",
    "coordinate", "坐标", "axis", "轴", "plot", "画图",
    "linear", "一次函数", "quadratic", "二次函数", "parabola",
    "number line", "数轴", "slope", "斜率", "intercept",
    "polygon", "多边形", "square", "正方形", "rectangle", "矩形",
    "tangent", "切线", "radius", "半径", "diameter", "直径",
    "交点", "intersection", "vertex", "顶点", "对称轴",
    "axis of symmetry", "抛物线", "曲线", "curve", "直线",
    "line", "方程", "equation", "求解", "solve", "plot",
    "直角", "坐标轴", "坐标系", "笛卡尔",
}


def _is_geometry_problem(text: str) -> bool:
    lower = text.lower()
    for kw in _GEO_KEYWORDS:
        if kw in lower:
            return True
    return False
