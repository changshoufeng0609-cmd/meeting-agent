#!/usr/bin/env python3
"""Minimal Markdown -> .docx converter for meeting summaries.

Handles: # / ## / ### headings, '- ' bullet lists, pipe tables,
'> ' blockquotes, **bold**, `inline code`. CJK-friendly fonts.

Usage: python md_to_docx.py <summary.md> [out.docx]
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor

BODY_FONT = "Microsoft JhengHei"   # 微軟正黑體 (Traditional Chinese)
MONO_FONT = "Menlo"
ACCENT = RGBColor(0x76, 0xB9, 0x00)   # NVIDIA green for headings


def set_cjk_font(run, name: str) -> None:
    run.font.name = name
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = rpr.makeelement(qn("w:rFonts"), {})
        rpr.append(rfonts)
    for attr in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
        rfonts.set(qn(attr), name)


_inline_re = re.compile(r"(\*\*.+?\*\*|`[^`]+`)")


def add_inline(paragraph, text: str, base_font: str = BODY_FONT, base_size: int = 11) -> None:
    """Render inline **bold** and `code` spans into a paragraph."""
    for part in _inline_re.split(text):
        if not part:
            continue
        if part.startswith("**") and part.endswith("**"):
            run = paragraph.add_run(part[2:-2])
            run.bold = True
            set_cjk_font(run, base_font)
            run.font.size = Pt(base_size)
        elif part.startswith("`") and part.endswith("`"):
            run = paragraph.add_run(part[1:-1])
            set_cjk_font(run, MONO_FONT)
            run.font.size = Pt(base_size - 1)
            run.font.color.rgb = RGBColor(0xC0, 0x39, 0x2B)
        else:
            run = paragraph.add_run(part)
            set_cjk_font(run, base_font)
            run.font.size = Pt(base_size)


def add_table(doc, rows: list[list[str]]) -> None:
    # rows[1] is the markdown separator (---|---), skip it
    header, body = rows[0], rows[2:]
    table = doc.add_table(rows=1, cols=len(header))
    table.style = "Light Grid Accent 1"
    table.alignment = WD_TABLE_ALIGNMENT.LEFT
    for i, cell_text in enumerate(header):
        cell = table.rows[0].cells[i]
        cell.paragraphs[0].clear()
        add_inline(cell.paragraphs[0], cell_text.strip(), base_size=10)
        for r in cell.paragraphs[0].runs:
            r.bold = True
    for row in body:
        cells = table.add_row().cells
        for i, cell_text in enumerate(row[: len(header)]):
            cells[i].paragraphs[0].clear()
            add_inline(cells[i].paragraphs[0], cell_text.strip(), base_size=10)
    doc.add_paragraph()


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python md_to_docx.py <summary.md> [out.docx]", file=sys.stderr)
        return 1
    src = Path(sys.argv[1]).expanduser().resolve()
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else src.with_suffix(".docx")

    doc = Document()
    normal = doc.styles["Normal"]
    normal.font.name = BODY_FONT
    normal.font.size = Pt(11)
    rpr = normal.element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = rpr.makeelement(qn("w:rFonts"), {})
        rpr.append(rfonts)
    for attr in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
        rfonts.set(qn(attr), BODY_FONT)

    lines = src.read_text(encoding="utf-8").splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].rstrip("\n")
        stripped = line.strip()

        # table block
        if stripped.startswith("|") and i + 1 < len(lines) and set(lines[i + 1].strip()) <= set("|-: "):
            block = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [c for c in lines[i].strip().strip("|").split("|")]
                block.append(cells)
                i += 1
            add_table(doc, block)
            continue

        if not stripped:
            i += 1
            continue

        if stripped.startswith("### "):
            p = doc.add_heading(level=3)
            add_inline(p, stripped[4:], base_size=12)
            for r in p.runs:
                r.font.color.rgb = ACCENT
        elif stripped.startswith("## "):
            p = doc.add_heading(level=2)
            add_inline(p, stripped[3:], base_size=14)
            for r in p.runs:
                r.font.color.rgb = ACCENT
        elif stripped.startswith("# "):
            p = doc.add_heading(level=1)
            add_inline(p, stripped[2:], base_size=18)
            for r in p.runs:
                r.font.color.rgb = ACCENT
        elif stripped.startswith("> "):
            p = doc.add_paragraph(style="Intense Quote")
            add_inline(p, stripped[2:], base_size=10)
        elif stripped.startswith("- "):
            p = doc.add_paragraph(style="List Bullet")
            add_inline(p, stripped[2:])
        else:
            p = doc.add_paragraph()
            add_inline(p, stripped)
        i += 1

    doc.save(str(out))
    print(f"✓ DOCX: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
