"""Export module — save study results in multiple formats.

All exports are pure Python (no external dependencies except matplotlib).
Supported formats: TXT, PNG, JPG, BMP, GIF, PDF, DOCX

The exported image includes the problem text overlaid on the diagram.
"""
from __future__ import annotations

import io
import os
import re
import zipfile
from pathlib import Path
from typing import Optional

from study_buddy.platform import diagrams_dir, copy_to_public


def export_all(
    title: str,
    explanation: str,
    problem_text: str = "",
    diagram_path: Optional[str] = None,
    out_dir: Optional[str] = None,
    formats: Optional[list[str]] = None,
) -> dict[str, str]:
    """Export explanation (+ diagram) in multiple formats.

    Args:
        title: Short title for the export
        explanation: Full explanation text
        problem_text: The original problem text (shown on exported images)
        diagram_path: Path to geometry diagram PNG (optional)
        out_dir: Output directory (default: ~/.hermes/study_exports/)
        formats: List of formats to export.
                 Default: [".txt", ".png", ".jpg", ".pdf", ".docx"]
                 Supported: .txt, .png, .jpg, .bmp, .gif, .pdf, .docx

    Returns:
        {".ext": "/path/to/file", ...}
    """
    if out_dir is None:
        out_dir = str(diagrams_dir() / "exports")
    Path(out_dir).mkdir(parents=True, exist_ok=True)

    if formats is None:
        formats = [".txt", ".png", ".jpg", ".pdf", ".docx"]

    stem = _stem_from_title(title)

    # Build the composite image once (if diagram exists) — used by multiple formats
    composite_path: Optional[str] = None
    if diagram_path and os.path.exists(diagram_path):
        _composite_path = f"{out_dir}/{stem}_composite.png"
        _make_composite_image(_composite_path, title, problem_text, diagram_path)
        composite_path = _composite_path

    results = {}

    for fmt in formats:
        fmt = fmt.strip().lower()
        if not fmt.startswith("."):
            fmt = f".{fmt}"

        out_path = f"{out_dir}/{stem}{fmt}"

        if fmt == ".txt":
            _export_txt(out_path, title, explanation)
        elif fmt in (".png", ".jpg", ".jpeg", ".bmp", ".gif"):
            _export_image(out_path, title, explanation, diagram_path, composite_path)
        elif fmt == ".pdf":
            _export_pdf(out_path, title, explanation, diagram_path, composite_path)
        elif fmt == ".docx":
            _export_docx(out_path, title, explanation, diagram_path, composite_path)
        else:
            continue  # unsupported format, skip

        if os.path.exists(out_path):
            results[fmt] = out_path

    return results


# ── Composite image: problem text + diagram ──────────────────────────────


def _make_composite_image(
    out_path: str,
    title: str,
    problem_text: str,
    diagram_path: str,
) -> None:
    """Create a composite image with problem text on top and diagram below."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.font_manager as fm
    from matplotlib.image import imread

    _register_cjk_font()

    # Read the original diagram
    img = imread(diagram_path)
    img_h, img_w = img.shape[:2]

    # Estimate text block height (proportional to text length)
    text_lines = max(1, title.count("\n") + 1) + max(1, problem_text.count("\n") + 1) + 2
    text_block_height = int(80 * text_lines)  # ~80px per line

    # Figure size: match diagram width, add text block on top
    dpi = 150
    fig_w = img_w / dpi
    fig_h = (img_h + text_block_height) / dpi

    fig, (ax_text, ax_img) = plt.subplots(
        2, 1, figsize=(fig_w, fig_h),
        gridspec_kw={"height_ratios": [text_block_height, img_h]},
    )
    fig.patch.set_facecolor("white")

    # ── Text block ──
    ax_text.axis("off")
    font_family = _cjk_family() or "sans-serif"

    text_content = f"[{title}]"
    if problem_text:
        text_content += f"\n\n{problem_text}"

    ax_text.text(
        0.02, 0.95, text_content,
        transform=ax_text.transAxes,
        fontsize=11,
        fontfamily=font_family,
        fontweight="bold",
        verticalalignment="top",
        horizontalalignment="left",
        color="#1a1a1a",
        linespacing=1.4,
    )

    # ── Diagram ──
    ax_img.axis("off")
    ax_img.imshow(img, aspect="auto")

    plt.tight_layout(pad=0.5)
    fig.savefig(out_path, dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)


# ── TXT ──────────────────────────────────────────────────────────────────


def _export_txt(path: str, title: str, explanation: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(_format_txt(title, explanation))


def _format_txt(title: str, explanation: str) -> str:
    import textwrap
    lines = [
        "=" * 60,
        f"  {title}",
        "=" * 60,
        "",
    ]
    for para in explanation.split("\n"):
        if para.strip():
            lines.extend(textwrap.wrap(para, width=72))
        else:
            lines.append("")
    lines.extend([
        "",
        "-" * 60,
        "Generated by AI Study Buddy",
    ])
    return "\n".join(lines)


# ── Image export (PNG, JPG, BMP, GIF) ────────────────────────────────────


def _export_image(
    path: str,
    title: str,
    explanation: str,
    diagram_path: Optional[str],
    composite_path: Optional[str],
) -> None:
    """Export as an image file.

    Uses the composite image if available (problem text + diagram),
    otherwise creates a text-as-image page.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    _register_cjk_font()

    # Determine format from extension
    fmt = Path(path).suffix.lstrip(".").lower()
    if fmt == "jpg":
        fmt = "jpeg"

    if composite_path and os.path.exists(composite_path):
        # Use the composite image directly
        from matplotlib.image import imread
        img = imread(composite_path)
        fig, ax = plt.subplots(figsize=(img.shape[1] / 100, img.shape[0] / 100))
        ax.axis("off")
        ax.imshow(img)
        fig.savefig(path, dpi=100, bbox_inches="tight", facecolor="white", format=fmt)
        plt.close(fig)
        return

    # No diagram: render explanation as text image
    font_family = _cjk_family() or "monospace"
    fig, ax = plt.subplots(figsize=(8.5, 11))
    ax.axis("off")

    text = f"{title}\n\n{explanation}"
    ax.text(
        0.05, 0.95, text,
        transform=ax.transAxes,
        fontsize=10,
        fontfamily=font_family,
        verticalalignment="top",
        horizontalalignment="left",
        linespacing=1.3,
    )
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="white", format=fmt)
    plt.close(fig)


# ── PDF ──────────────────────────────────────────────────────────────────


def _export_pdf(
    path: str,
    title: str,
    explanation: str,
    diagram_path: Optional[str],
    composite_path: Optional[str],
) -> None:
    """Create a multi-page PDF with explanation + diagram."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.font_manager as fm
    from matplotlib.backends.backend_pdf import PdfPages

    _register_cjk_font()
    font_family = _cjk_family() or "monospace"

    with PdfPages(path) as pdf:
        # Page 1: Explanation text
        fig, ax = plt.subplots(figsize=(8.5, 11))
        ax.axis("off")
        _write_text_page(ax, title, explanation, font_family)
        pdf.savefig(fig, dpi=150, facecolor="white")
        plt.close(fig)

        # Page 2: Composite image (or diagram)
        src = composite_path or diagram_path
        if src and os.path.exists(src):
            from matplotlib.image import imread
            img = imread(src)
            fig2, ax2 = plt.subplots(figsize=(8.5, 11))
            ax2.axis("off")
            ax2.imshow(img, aspect="auto")
            pdf.savefig(fig2, dpi=150, facecolor="white")
            plt.close(fig2)


def _write_text_page(ax, title: str, explanation: str, font_family: str):
    """Write explanation text onto a matplotlib axis (for PDF)."""
    import textwrap
    lines = []
    lines.append(title)
    lines.append("")
    for para in explanation.split("\n"):
        if para.strip():
            lines.extend(textwrap.wrap(para, width=80))
        else:
            lines.append("")
    text = "\n".join(lines)

    ax.text(
        0.05, 0.95, text,
        transform=ax.transAxes,
        fontsize=10,
        fontfamily=font_family,
        verticalalignment="top",
        horizontalalignment="left",
        linespacing=1.3,
    )


# ── DOCX (pure Python, no lxml) ─────────────────────────────────────────


def _export_docx(
    path: str,
    title: str,
    explanation: str,
    diagram_path: Optional[str],
    composite_path: Optional[str],
) -> None:
    """Generate a .docx file using only stdlib (zipfile + xml.etree)."""
    from xml.sax.saxutils import escape as xml_escape

    src = composite_path or diagram_path

    # Build ZIP
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", _DOCX_CONTENT_TYPES)
        zf.writestr("_rels/.rels", _DOCX_RELS)

        if src and os.path.exists(src):
            zf.write(src, "word/media/diagram.png")
            zf.writestr("word/document.xml", _make_docx_with_image(title, explanation, src))
            zf.writestr("word/_rels/document.xml.rels", _DOCX_IMAGE_RELS)
        else:
            wrapped = _simple_wrap(f"{title}\n\n{explanation}", width=72)
            body_text = "\n".join(wrapped)
            body = xml_escape(body_text).replace(
                "\n", '</w:t><w:br/><w:t xml:space="preserve">'
            )
            doc_xml = _DOCX_TEMPLATE.format(title=xml_escape(title), body=body)
            zf.writestr("word/document.xml", doc_xml)


def _make_docx_with_image(title: str, explanation: str, image_path: str) -> str:
    from xml.sax.saxutils import escape as xml_escape
    wrapped = _simple_wrap(f"{title}\n\n{explanation}", width=72)
    body = xml_escape("\n".join(wrapped)).replace(
        "\n", '</w:t><w:br/><w:t xml:space="preserve">'
    )
    return _DOCX_WITH_IMAGE.format(title=xml_escape(title), body=body)


_DOCX_TEMPLATE = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
            xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <w:body>
    <w:p>
      <w:pPr><w:jc w:val="center"/><w:rPr><w:sz w:val="28"/><w:b/></w:rPr></w:pPr>
      <w:r><w:rPr><w:sz w:val="28"/><w:b/></w:rPr><w:t xml:space="preserve">{title}</w:t></w:r>
    </w:p>
    <w:p><w:r><w:br/></w:r></w:p>
    <w:p>
      <w:r><w:t xml:space="preserve">{body}</w:t></w:r>
    </w:p>
  </w:body>
</w:document>'''

_DOCX_WITH_IMAGE = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
            xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
            xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
            xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
            xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">
  <w:body>
    <w:p>
      <w:pPr><w:jc w:val="center"/><w:rPr><w:sz w:val="28"/><w:b/></w:rPr></w:pPr>
      <w:r><w:rPr><w:sz w:val="28"/><w:b/></w:rPr><w:t xml:space="preserve">{title}</w:t></w:r>
    </w:p>
    <w:p><w:r><w:br/></w:r></w:p>
    <w:p>
      <w:r><w:t xml:space="preserve">{body}</w:t></w:r>
    </w:p>
    <w:p><w:r><w:br/></w:r></w:p>
    <w:p>
      <w:r>
        <w:drawing>
          <wp:inline distT="0" distB="0" distL="0" distR="0">
            <wp:extent cx="4572000" cy="4572000"/>
            <wp:effectExtent l="0" t="0" r="0" b="0"/>
            <wp:docPr id="1" name="Diagram"/>
            <wp:cNvGraphicFramePr/>
            <a:graphic>
              <a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">
                <pic:pic>
                  <pic:nvPicPr>
                    <pic:cNvPr id="0" name="Diagram"/>
                    <pic:cNvPicPr/>
                  </pic:nvPicPr>
                  <pic:blipFill>
                    <a:blip r:embed="rId2"/>
                    <a:stretch><a:fillRect/></a:stretch>
                  </pic:blipFill>
                  <pic:spPr>
                    <a:xfrm>
                      <a:off x="0" y="0"/>
                      <a:ext cx="4572000" cy="4572000"/>
                    </a:xfrm>
                    <a:prstGeom prst="rect"/>
                  </pic:spPr>
                </pic:pic>
              </a:graphicData>
            </a:graphic>
          </wp:inline>
        </w:drawing>
      </w:r>
    </w:p>
  </w:body>
</w:document>'''

_DOCX_CONTENT_TYPES = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Default Extension="png" ContentType="image/png"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>'''

_DOCX_RELS = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>'''

_DOCX_IMAGE_RELS = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="document.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/diagram.png"/>
</Relationships>'''


# ── Helpers ──────────────────────────────────────────────────────────────


def _stem_from_title(title: str) -> str:
    stem = re.sub(r"[^\w\s-]", "", title).strip().replace(" ", "_")[:50]
    return stem or "study_export"


def _simple_wrap(text: str, width: int = 72) -> list[str]:
    import textwrap
    result = []
    for para in text.split("\n"):
        if para.strip():
            result.extend(textwrap.wrap(para, width=width))
        else:
            result.append("")
    return result


def _cjk_font_path() -> Optional[str]:
    """Find a CJK font on the current platform."""
    from study_buddy.platform import cjk_font_path as _cfp
    return _cfp()


def _register_cjk_font():
    """Register CJK font with matplotlib."""
    import matplotlib.font_manager as fm
    cjk = _cjk_font_path()
    if cjk:
        fm.fontManager.addfont(cjk)


def _cjk_family() -> Optional[str]:
    """Get the CJK font family name for matplotlib."""
    cjk = _cjk_font_path()
    if not cjk:
        return None
    fname = Path(cjk).stem
    if "Noto" in fname:
        return "Noto Sans CJK JP"
    if "msyh" in fname or "YaHei" in fname:
        return "Microsoft YaHei"
    if "simsun" in fname:
        return "SimSun"
    if "simhei" in fname:
        return "SimHei"
    return None
