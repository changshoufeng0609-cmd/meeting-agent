#!/usr/bin/env python3
"""
Render a Markdown file to PDF using headless Chromium (Playwright).

Usage:
    python render_pdf.py <input.md> [<output.pdf>]

Chromium reliably embeds all CJK glyphs (PingFang TC) into the PDF,
avoiding the WeasyPrint+TTC font subsetting issue that drops characters
in Adobe / Preview.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import markdown
from playwright.sync_api import sync_playwright

CSS = """
* { box-sizing: border-box; }
html, body {
  margin: 0;
  padding: 0;
  color: #000;
}
body {
  font-family: "PingFang TC", "Heiti TC", "Hiragino Sans CNS",
               "Noto Sans CJK TC", "Microsoft JhengHei", sans-serif;
  font-size: 10.5pt;
  line-height: 1.65;
  color: #000;
  padding: 4mm 0;
}
h1 {
  font-size: 20pt;
  border-bottom: 2px solid #000;
  padding-bottom: 6px;
  margin: 0 0 14px;
  color: #000;
}
h2 {
  font-size: 14pt;
  border-bottom: 1px solid #999;
  padding-bottom: 4px;
  margin: 22px 0 10px;
  color: #000;
}
h3 {
  font-size: 12pt;
  margin: 18px 0 8px;
  color: #000;
}
p { margin: 6px 0; color: #000; }
ul, ol { margin: 6px 0 6px 24px; padding: 0; color: #000; }
li { margin: 3px 0; color: #000; }
strong { color: #000; font-weight: 700; }
em { color: #000; }
blockquote {
  border-left: 3px solid #999;
  padding: 4px 12px;
  margin: 8px 0;
  color: #000;
  background: #f5f5f5;
}
table {
  border-collapse: collapse;
  width: 100%;
  margin: 10px 0;
  font-size: 10pt;
  color: #000;
  page-break-inside: avoid;
}
th, td {
  border: 1px solid #999;
  padding: 6px 9px;
  text-align: left;
  vertical-align: top;
  color: #000;
}
th { background: #ececec; font-weight: 700; color: #000; }
code {
  background: #f0f0f0;
  padding: 1px 5px;
  border-radius: 3px;
  font-family: "SF Mono", Menlo, monospace;
  font-size: 9.5pt;
  color: #000;
}
pre {
  background: #f5f5f5;
  border: 1px solid #ccc;
  border-radius: 4px;
  padding: 10px;
  overflow-x: auto;
  font-size: 9pt;
  color: #000;
  page-break-inside: avoid;
}
pre code { background: transparent; color: #000; padding: 0; }
a { color: #000; text-decoration: underline; }
hr { border: 0; border-top: 1px solid #999; margin: 18px 0; }
h1, h2, h3 { page-break-after: avoid; }
"""

HTML_TEMPLATE = """<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>{css}</style>
</head>
<body>{body}</body>
</html>
"""

FOOTER_TEMPLATE = (
    '<div style="font-size:9pt; color:#000; width:100%; text-align:center; '
    'font-family:\'PingFang TC\',sans-serif;">'
    '<span class="pageNumber"></span> / <span class="totalPages"></span>'
    "</div>"
)


def render(md_path: Path, pdf_path: Path) -> None:
    md_text = md_path.read_text(encoding="utf-8")
    html_body = markdown.markdown(md_text, extensions=["tables", "fenced_code", "sane_lists"])
    full_html = HTML_TEMPLATE.format(title=md_path.stem, css=CSS, body=html_body)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_page()
            page.set_content(full_html, wait_until="domcontentloaded")
            page.emulate_media(media="print")
            page.pdf(
                path=str(pdf_path),
                format="A4",
                margin={"top": "20mm", "right": "18mm", "bottom": "20mm", "left": "18mm"},
                print_background=True,
                display_header_footer=True,
                header_template="<div></div>",
                footer_template=FOOTER_TEMPLATE,
            )
        finally:
            browser.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Markdown file to render")
    parser.add_argument("output", type=Path, nargs="?", help="Output PDF (default: <input>.pdf)")
    args = parser.parse_args()

    md_path: Path = args.input.expanduser().resolve()
    if not md_path.exists():
        print(f"[ERROR] not found: {md_path}", file=sys.stderr)
        return 1

    pdf_path: Path = args.output.expanduser().resolve() if args.output else md_path.with_suffix(".pdf")
    render(md_path, pdf_path)
    print(f"✓ PDF: {pdf_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
