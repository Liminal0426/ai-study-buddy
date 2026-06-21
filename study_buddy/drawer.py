"""High-precision geometry drawing module.

Takes structured descriptions and renders accurate mathematical
diagrams using matplotlib.  NOT an LLM image generator — every
pixel is computed from the exact math.

Supported shapes
────────────────
• Linear functions      y = kx + b
• Quadratic functions   y = ax² + bx + c
• Circles               (x − h)² + (y − k)² = r²
• Number lines          tick marks with labels
• Points / intersections
• Polygons, angles, arrows
• Grids, axes, labels
"""
from __future__ import annotations

import re
import io
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import matplotlib
matplotlib.use("Agg")  # no display needed (headless safe)
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np

from study_buddy.platform import cjk_font_path, diagrams_dir, terminal_preview, copy_to_public

# ── Register CJK font (cross-platform) ──
_CJK_FONT = cjk_font_path()
if _CJK_FONT:
    fm.fontManager.addfont(_CJK_FONT)
    # Use the font's family name — varies by platform
    _fname = Path(_CJK_FONT).stem
    if "Noto" in _fname:
        plt.rcParams["font.family"] = "Noto Sans CJK JP"
    elif "msyh" in _fname or "YaHei" in _fname:
        plt.rcParams["font.family"] = "Microsoft YaHei"
    elif "simsun" in _fname:
        plt.rcParams["font.family"] = "SimSun"
    elif "simhei" in _fname:
        plt.rcParams["font.family"] = "SimHei"
    else:
        plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["axes.unicode_minus"] = False


# ── Public API ────────────────────────────────────────────────────────


def render_geometry(instructions: Dict[str, Any]) -> str:
    """Render a geometry diagram from structured instructions.

    ``instructions`` format (produced by the AI solver)::

        {
            "title": str,               # optional, shown above plot
            "grid": bool,               # default True
            "equal_axis": bool,         # default True (square aspect)
            "x_range": [float, float],  # default [-10, 10]
            "y_range": [float, float],  # default [-10, 10]
            "elements": [
                {
                    "type": "function",
                    "expr": "2*x + 1",
                    "label": "y = 2x + 1",
                    "color": "blue",
                    "style": "-",        # -, --, :, -.
                },
                {
                    "type": "circle",
                    "center": [0, 0],
                    "radius": 3,
                    "label": "x² + y² = 9",
                    "color": "red",
                },
                {
                    "type": "number_line",
                    "min": -5,
                    "max": 5,
                    "ticks": [-5, -4, -3, -2, -1, 0, 1, 2, 3, 4, 5],
                    "highlight": [0, 2, 5],  # optional: mark these ticks
                },
                {
                    "type": "point",
                    "x": 2,
                    "y": 5,
                    "label": "A(2,5)",
                    "color": "green",
                },
                {
                    "type": "segment",
                    "x1": 0, "y1": 0,
                    "x2": 4, "y2": 3,
                    "label": "AB",
                    "color": "purple",
                },
                {
                    "type": "shade",
                    "x_start": -2,
                    "x_end": 3,
                    "above_func": "x**2",   # shade area above this curve
                    "below_func": "0",      # and below this one
                    "color": "yellow",
                    "alpha": 0.3,
                },
            ]
        }

    Returns the **absolute path** to the rendered PNG.
    """
    fig, ax = plt.subplots(figsize=(8, 8))

    # ── ranges ──
    xr = instructions.get("x_range", [-10, 10])
    yr = instructions.get("y_range", [-10, 10])
    ax.set_xlim(xr)
    ax.set_ylim(yr)

    # ── grid ──
    if instructions.get("grid", True):
        ax.grid(True, linestyle=":", alpha=0.4)
    if instructions.get("equal_axis", True):
        ax.set_aspect("equal", adjustable="box")

    # ── axis labels ──
    ax.axhline(0, color="black", linewidth=0.8)
    ax.axvline(0, color="black", linewidth=0.8)
    ax.set_xlabel("x")
    ax.set_ylabel("y")

    # ── title ──
    if title := instructions.get("title"):
        ax.set_title(title, fontsize=14, fontweight="bold")

    # ── elements ──
    for el in instructions.get("elements", []):
        _draw_element(ax, el, xr)

    ax.legend(loc="best", fontsize=9)

    # ── save ──
    out_dir = diagrams_dir()
    out_path = out_dir / f"geometry_{_next_id()}.png"
    fig.savefig(str(out_path), dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    # ── terminal preview (if chafa available) ──
    terminal_preview(str(out_path))

    # ── copy to public dir (Downloads on Android) ──
    copy_to_public(out_path)

    return str(out_path)


def render_function(
    expr: str,
    x_range: Tuple[float, float] = (-10, 10),
    label: Optional[str] = None,
    title: Optional[str] = None,
) -> str:
    """Quick helper: draw a single function and return the image path."""
    return render_geometry({
        "title": title or f"y = {expr}",
        "x_range": list(x_range),
        "y_range": list(_auto_y_range(expr, x_range)),
        "elements": [
            {"type": "function", "expr": expr, "label": label or f"y = {expr}"}
        ],
    })


def render_number_line(
    ticks: List[Union[int, float]],
    min_val: Optional[Union[int, float]] = None,
    max_val: Optional[Union[int, float]] = None,
    highlight: Optional[List[Union[int, float]]] = None,
    title: Optional[str] = None,
) -> str:
    """Draw a number line."""
    if min_val is None:
        min_val = min(ticks) - 1
    if max_val is None:
        max_val = max(ticks) + 1
    return render_geometry({
        "title": title or "数轴",
        "x_range": [float(min_val), float(max_val)],
        "y_range": [-1, 1],
        "equal_axis": False,
        "elements": [
            {
                "type": "number_line",
                "min": float(min_val),
                "max": float(max_val),
                "ticks": [float(t) for t in ticks],
                "highlight": [float(t) for t in (highlight or [])],
            }
        ],
    })


# ── Element drawing ───────────────────────────────────────────────────


def _draw_element(ax: Any, el: Dict[str, Any], xr: List[float]) -> None:
    el_type = el.get("type", "")
    color = el.get("color", "blue")
    style = el.get("style", "-")
    label = el.get("label", "")

    if el_type == "function":
        expr = el.get("expr", "0")
        xs = np.linspace(xr[0], xr[1], 2000)
        try:
            ys = _safe_eval(expr, xs)
            ax.plot(xs, ys, color=color, linestyle=style, linewidth=1.5, label=label or expr)
        except Exception:
            pass

    elif el_type == "circle":
        cx, cy = el.get("center", [0, 0])
        r = el.get("radius", 1)
        circle = plt.Circle((cx, cy), r, fill=False, color=color,
                            linewidth=1.5, label=label)
        ax.add_patch(circle)

    elif el_type == "number_line":
        tmin = el.get("min", -5)
        tmax = el.get("max", 5)
        ticks = el.get("ticks", [])
        highlight = el.get("highlight", [])

        # Draw the line
        ax.plot([tmin, tmax], [0, 0], color="black", linewidth=1.5)
        # Arrow ends
        ax.annotate("", xy=(tmax + 0.3, 0), xytext=(tmax, 0),
                    arrowprops=dict(arrowstyle="->", color="black", lw=1.5))
        ax.annotate("", xy=(tmin - 0.3, 0), xytext=(tmin, 0),
                    arrowprops=dict(arrowstyle="->", color="black", lw=1.5))

        # Ticks
        for t in ticks:
            ax.plot([t, t], [-0.2, 0.2], color="black", linewidth=1.0)
            ax.text(t, -0.4, str(int(t)) if t == int(t) else str(t),
                    ha="center", va="top", fontsize=9)

        # Highlighted ticks (coloured dots)
        for t in highlight:
            if t in ticks:
                ax.plot(t, 0, "o", color=color, markersize=8, zorder=5)
                ax.text(t, 0.25, f"●{int(t)}" if t == int(t) else f"●{t}",
                        ha="center", va="bottom", fontsize=9, color=color)

        # Hide y-axis
        ax.set_yticks([])
        ax.set_ylabel("")

    elif el_type == "point":
        x, y = el.get("x", 0), el.get("y", 0)
        ax.plot(x, y, "o", color=color, markersize=6, zorder=5, label=label)
        if label:
            offset_x = el.get("label_offset_x", 0.3)
            offset_y = el.get("label_offset_y", 0.3)
            ax.text(x + offset_x, y + offset_y, label, fontsize=10, color=color)

    elif el_type == "segment":
        x1, y1 = el.get("x1", 0), el.get("y1", 0)
        x2, y2 = el.get("x2", 0), el.get("y2", 0)
        ax.plot([x1, x2], [y1, y2], color=color, linewidth=1.5, label=label)

    elif el_type == "shade":
        xs = np.linspace(
            el.get("x_start", xr[0]),
            el.get("x_end", xr[1]),
            500,
        )
        try:
            above = _safe_eval(el.get("above_func", "0"), xs)
            below = _safe_eval(el.get("below_func", "0"), xs)
            ax.fill_between(xs, below, above, color=color,
                            alpha=el.get("alpha", 0.3), label=label)
        except Exception:
            pass

    elif el_type == "polygon":
        verts = el.get("vertices", [])
        if verts:
            xs = [v[0] for v in verts] + [verts[0][0]]
            ys = [v[1] for v in verts] + [verts[0][1]]
            ax.plot(xs, ys, color=color, linewidth=1.5, label=label)
            ax.fill(xs, ys, color=color, alpha=el.get("alpha", 0.15))

    elif el_type == "arrow":
        x, y = el.get("x", 0), el.get("y", 0)
        dx, dy = el.get("dx", 1), el.get("dy", 0)
        ax.arrow(x, y, dx, dy,
                 head_width=el.get("head_width", 0.2),
                 head_length=el.get("head_length", 0.2),
                 fc=color, ec=color, linewidth=1.2, label=label)

    elif el_type == "angle":
        """Draw an angle arc between two rays from a vertex.
        
        Required keys:
          vertex: [x, y]        — vertex point (e.g. angle B)
          ray1: [x, y]          — point on one ray (e.g. A)
          ray2: [x, y]          — point on the other ray (e.g. C)
          label: str            — e.g. "∠ABC = 30°"
          arc_radius: float     — radius of the angle arc (default 0.5)
        """
        vx, vy = el.get("vertex", [0, 0])
        r1x, r1y = el.get("ray1", [1, 0])
        r2x, r2y = el.get("ray2", [0, 1])
        arc_r = el.get("arc_radius", 0.5)

        # Compute angles from vertex
        a1 = np.arctan2(r1y - vy, r1x - vx)
        a2 = np.arctan2(r2y - vy, r2x - vx)

        # Ensure we draw the smaller angle
        angle_diff = (a2 - a1 + np.pi) % (2 * np.pi) - np.pi
        if angle_diff < 0:
            a1, a2 = a2, a1
            angle_diff = -angle_diff

        if angle_diff > 0.001:
            theta = np.linspace(a1, a2, 50)
            arc_x = vx + arc_r * np.cos(theta)
            arc_y = vy + arc_r * np.sin(theta)
            ax.plot(arc_x, arc_y, color=color, linewidth=1.5)

        # Label at midpoint of arc
        mid_angle = (a1 + a2) / 2
        label_offset = el.get("label_offset", 0.2)
        lx = vx + (arc_r + label_offset) * np.cos(mid_angle)
        ly = vy + (arc_r + label_offset) * np.sin(mid_angle)
        if label:
            ax.text(lx, ly, label, fontsize=9, ha="center", va="center", color=color)


# ── Helpers ───────────────────────────────────────────────────────────


_counter: int = 0


def _next_id() -> int:
    global _counter
    _counter += 1
    return _counter


def _safe_eval(expr: str, xs: np.ndarray) -> np.ndarray:
    """Evaluate a mathematical expression safely.

    Recognised: x, pi, e, sin, cos, tan, sqrt, abs, log.
    """
    import math
    allowed = {
        "x": xs,
        "pi": np.pi,
        "e": np.e,
        "sin": np.sin,
        "cos": np.cos,
        "tan": np.tan,
        "sqrt": np.sqrt,
        "abs": np.abs,
        "log": np.log,
        "log10": np.log10,
        "exp": np.exp,
        "**": pow,
    }
    # Replace common notations
    cleaned = expr.replace("^", "**")
    return eval(cleaned, {"__builtins__": {}}, allowed)


def _auto_y_range(expr: str, x_range: Tuple[float, float]) -> Tuple[float, float]:
    """Estimate a reasonable y-range for a function."""
    xs = np.linspace(x_range[0], x_range[1], 200)
    try:
        ys = _safe_eval(expr, xs)
        ys = ys[np.isfinite(ys)]
        if len(ys) == 0:
            return (-10, 10)
        margin = (ys.max() - ys.min()) * 0.1 or 2
        return (float(ys.min()) - margin, float(ys.max()) + margin)
    except Exception:
        return (-10, 10)
