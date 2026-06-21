"""Platform detection and path resolution for cross-platform support.

Android (Termux) and Windows (PowerShell) — one codebase, both platforms.
"""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


def is_android() -> bool:
    """Detect Android Termux environment."""
    return "ANDROID_ROOT" in os.environ or "TERMUX_VERSION" in os.environ


def is_windows() -> bool:
    return platform.system() == "Windows"


def is_termux() -> bool:
    """Has termux-specific tools (camera, API)."""
    return is_android() and shutil.which("termux-camera-photo") is not None


def downloads_dir() -> Path:
    """Cross-platform Downloads folder."""
    if is_android():
        # Android public download dir
        sdcard = Path("/sdcard/Download")
        if sdcard.exists():
            return sdcard
        # Fallback: Termux private dir
        return Path.home() / "downloads"
    elif is_windows():
        return Path(os.environ.get("USERPROFILE", "C:/")) / "Downloads"
    else:
        return Path.home() / "Downloads"


def diagrams_dir() -> Path:
    """Where geometry diagrams are saved."""
    base = Path.home() / ".hermes" / "study_diagrams"
    base.mkdir(parents=True, exist_ok=True)
    return base


def memory_db_path() -> Path:
    """Path for the study memory SQLite database."""
    base = Path.home() / ".hermes"
    if is_windows():
        base = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "hermes"
    base.mkdir(parents=True, exist_ok=True)
    return base / "study_memory.db"


def copy_to_public(path: Path) -> Path | None:
    """Copy a file to a publicly accessible location so the user can open it.

    On Android: copies to /sdcard/Download/
    On Windows: no action needed (files are already accessible)
    Returns the public path or None if already accessible.
    """
    if is_android():
        dst = downloads_dir() / path.name
        try:
            import shutil as _su
            _su.copy(str(path), str(dst))
            return dst
        except Exception:
            return None
    return None  # Windows: files in home are already accessible


def take_photo(output_path: str) -> tuple[bool, str]:
    """Take a photo using platform-appropriate camera.

    Returns (success: bool, message_or_path: str)
    On success, message_or_path is the photo file path.
    """
    if is_termux():
        r = subprocess.run(
            ["termux-camera-photo", output_path],
            capture_output=True, text=True, timeout=15,
        )
        if r.returncode == 0:
            return (True, output_path)
        return (False, r.stderr.strip() or r.stdout.strip() or "Camera error")

    if is_windows():
        try:
            import cv2
            cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                return (False, "No webcam found (cv2.VideoCapture(0) failed)")
            ret, frame = cap.read()
            cap.release()
            if ret:
                cv2.imwrite(output_path, frame)
                return (True, output_path)
            return (False, "Could not capture frame from webcam")
        except ImportError:
            return (False, "OpenCV not installed. Run: pip install opencv-python")
        except Exception as e:
            return (False, f"Webcam error: {e}")

    return (False, "No camera support on this platform")


def pick_image() -> tuple[bool, str]:
    """Open a file picker dialog to select an image from storage.

    Windows: uses tkinter filedialog (included with Python).
    Android/other: prints instructions for the user to type a path.

    Returns (success: bool, path_or_message)
    """
    if is_windows():
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()  # Hide the main window
            root.attributes("-topmost", True)  # Bring dialog to front
            path = filedialog.askopenfilename(
                title="Select an image file",
                filetypes=[
                    ("Image files", "*.jpg *.jpeg *.png *.bmp *.gif *.webp"),
                    ("All files", "*.*"),
                ],
            )
            root.destroy()
            if path:
                return (True, path)
            return (False, "No file selected")
        except Exception as e:
            return (False, f"File dialog error: {e}")

    # Non-Windows: prompt user to type path
    return (False, "请在手机上拍照或输入图片路径")


def terminal_preview(image_path: str) -> bool:
    """Display an image in the terminal using chafa (if available).

    Returns True if preview was shown.
    """
    if not shutil.which("chafa"):
        return False
    try:
        term_width = shutil.get_terminal_size((80, 24)).columns
        size = max(30, term_width // 2)
        subprocess.run(
            ["chafa", "--symbols", "all", "--color-space", "rgb",
             "--dither", "none", "--size", f"{size}x{size//2}",
             image_path],
            stderr=subprocess.DEVNULL,
        )
        return True
    except Exception:
        return False


def cjk_font_path() -> str | None:
    """Find a CJK-capable font on the current platform."""
    candidates = []

    if is_android():
        candidates = [
            "/system/fonts/NotoSansCJK-Regular.ttc",
            "/system/fonts/NotoSansSC-Regular.otf",
            "/system/fonts/DroidSansFallback.ttf",
        ]
    elif is_windows():
        windir = os.environ.get("WINDIR", "C:\\Windows")
        candidates = [
            os.path.join(windir, "Fonts", "msyh.ttc"),        # Microsoft YaHei
            os.path.join(windir, "Fonts", "simsun.ttc"),       # SimSun
            os.path.join(windir, "Fonts", "simhei.ttf"),       # SimHei
        ]
    else:
        candidates = [
            "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        ]

    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def install_chafa() -> tuple[bool, str]:
    """Attempt to install chafa on the current platform."""
    if is_termux():
        r = subprocess.run(
            ["pkg", "install", "-y", "chafa"],
            capture_output=True, text=True, timeout=120,
        )
        if r.returncode == 0:
            return (True, "chafa installed via pkg")
        return (False, f"pkg install failed: {r.stderr.strip()[:200]}")
    if is_windows():
        # Try winget or choco
        for mgr in ["winget", "choco"]:
            if shutil.which(mgr):
                r = subprocess.run(
                    [mgr, "install", "chafa" if mgr == "winget" else "chafa"],
                    capture_output=True, text=True, timeout=60,
                )
                if r.returncode == 0:
                    return (True, f"chafa installed via {mgr}")
                return (False, f"{mgr} install failed: {r.stderr.strip()[:200]}")
        return (False, "No package manager found. Install chafa manually, or install via winget/choco.")
    return (False, "No automatic install for this platform. Install chafa manually.")
