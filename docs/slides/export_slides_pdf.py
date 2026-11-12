"""
Generic Markdown-to-PDF widescreen slide deck converter.

Features:
- Splits slides on `<!-- slide -->` or `---` horizontal rules
- Strips outer ````carousel fences if present
- Automatically builds a cover slide if a top-level `# Title` precedes the first `## ` slide,
  deriving table-of-contents pills dynamically from each slide's `##` heading
- Renders ```mermaid blocks via Mermaid.js, GitHub-style `> [!NOTE|TIP|IMPORTANT|WARNING|CAUTION]`
  alerts, fenced code blocks, and tables
"""

import argparse
import html
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import markdown


ALERT_ICONS = {
    "NOTE": "ℹ",
    "TIP": "💡",
    "IMPORTANT": "⚠",
    "WARNING": "▲",
    "CAUTION": "⛔",
}

PILL_CLASSES = ("blue", "teal", "red", "purple", "gold")


def find_browser_binary() -> str:
    """Locate a headless-capable Chromium/Chrome binary across platforms."""
    for cmd in ("google-chrome", "chromium", "chromium-browser", "chrome", "msedge"):
        found = shutil.which(cmd)
        if found:
            return found

    mac_candidates = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    ]
    for candidate in mac_candidates:
        if Path(candidate).is_file():
            return candidate

    raise FileNotFoundError(
        "Could not find Chrome/Chromium binary. Install Google Chrome or Chromium."
    )


def convert_md_slide_to_html(md_text: str) -> str:
    """Convert a single markdown slide (including ```mermaid and GitHub alerts) to HTML."""
    mermaid_blocks: list[str] = []

    def _stash_mermaid(match: re.Match) -> str:
        idx = len(mermaid_blocks)
        mermaid_blocks.append(match.group(1).strip())
        return f"\n\n@@MERMAID_BLOCK_{idx}@@\n\n"

    md_text = re.sub(
        r"```mermaid\s*\n(.*?)```",
        _stash_mermaid,
        md_text,
        flags=re.DOTALL,
    )

    def _convert_alert(match: re.Match) -> str:
        kind = match.group(1).upper()
        icon = ALERT_ICONS.get(kind, "•")
        body_lines = [
            re.sub(r"^>\s?", "", line)
            for line in match.group(2).strip().splitlines()
        ]
        body_html = markdown.markdown(
            "\n".join(body_lines),
            extensions=["extra", "fenced_code", "tables"],
        )
        return (
            f'<div class="callout callout-{kind.lower()}">'
            f'<div class="callout-title">{icon} {kind}</div>'
            f'<div class="callout-body">{body_html}</div>'
            f"</div>"
        )

    md_text = re.sub(
        r"^>\s*\[!(IMPORTANT|NOTE|TIP|WARNING|CAUTION)\]\s*\n((?:^>.*(?:\n|$))+)",
        _convert_alert,
        md_text,
        flags=re.MULTILINE,
    )

    rendered = markdown.markdown(
        md_text,
        extensions=["extra", "fenced_code", "tables"],
    )

    for idx, m_code in enumerate(mermaid_blocks):
        escaped = html.escape(m_code)
        block_html = f'<div class="mermaid-container"><pre class="mermaid">{escaped}</pre></div>'
        rendered = rendered.replace(f"<p>@@MERMAID_BLOCK_{idx}@@</p>", block_html)
        rendered = rendered.replace(f"@@MERMAID_BLOCK_{idx}@@", block_html)

    return rendered


def extract_heading(slide_md: str) -> str | None:
    """Extract the first markdown heading from a slide for navigation pills."""
    m = re.search(r"^#{1,3}\s+(.+?)\s*$", slide_md, flags=re.MULTILINE)
    if not m:
        return None
    # Strip inline markdown backticks/links for clean pill text
    heading = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", m.group(1))
    return heading.replace("`", "").strip()


def build_html_deck(
    md_path: Path,
    separator_pattern: str = r"^\s*(?:<!--\s*slide\s*-->|---)\s*$",
) -> str:
    raw = md_path.read_text(encoding="utf-8")

    # Strip outer ````carousel fences if present
    lines = [line for line in raw.splitlines() if not line.strip().startswith("````")]
    cleaned = "\n".join(lines).strip()

    # Check if a top-level `# Title` (and optional intro text) precedes the first `## ` heading
    deck_title = md_path.stem.replace("_", " ").replace("-", " ").title()
    cover_intro_md = ""
    has_auto_cover = False

    m_top = re.match(r"^#\s+(.+?)\s*\n+(.*?)(?=^##\s|\Z)", cleaned, flags=re.DOTALL | re.MULTILINE)
    if m_top and not re.search(separator_pattern, m_top.group(2), flags=re.MULTILINE):
        deck_title = m_top.group(1).strip()
        cover_intro_md = m_top.group(2).strip()
        cleaned = cleaned[m_top.end() :].strip()
        has_auto_cover = True

    raw_slides = [
        s.strip()
        for s in re.split(separator_pattern, cleaned, flags=re.MULTILINE)
        if s.strip()
    ]

    slide_sections: list[str] = []

    if has_auto_cover:
        headings = [extract_heading(s) for s in raw_slides]
        pills_html = "".join(
            f'<span class="pill {PILL_CLASSES[i % len(PILL_CLASSES)]}">{html.escape(h)}</span>'
            for i, h in enumerate(headings)
            if h
        )
        intro_html = (
            f'<div class="subtitle">{convert_md_slide_to_html(cover_intro_md)}</div>'
            if cover_intro_md
            else ""
        )
        slide_sections.append(
            f"""
            <section class="slide title-slide">
                <div class="top-bar"></div>
                <div class="title-content">
                    <div class="badge">{html.escape(md_path.stem.upper())}</div>
                    <h1>{html.escape(deck_title)}</h1>
                    {intro_html}
                    <div class="pill-row">{pills_html}</div>
                </div>
                <div class="slide-footer">
                    <span>{html.escape(md_path.name)}</span>
                    <span>Cover</span>
                </div>
            </section>
            """
        )

    total = len(raw_slides)
    for idx, s_md in enumerate(raw_slides, start=1):
        body_html = convert_md_slide_to_html(s_md)
        slide_sections.append(
            f"""
            <section class="slide content-slide">
                <div class="top-bar"></div>
                <div class="slide-inner">
                    {body_html}
                </div>
                <div class="slide-footer">
                    <span>{html.escape(deck_title)}</span>
                    <span>{idx} / {total}</span>
                </div>
            </section>
            """
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>{html.escape(deck_title)}</title>
<style>
  @page {{
    size: 13.333in 7.5in;
    margin: 0;
  }}
  * {{
    box-sizing: border-box;
    -webkit-print-color-adjust: exact !important;
    print-color-adjust: exact !important;
  }}
  html, body {{
    margin: 0;
    padding: 0;
    background: #0f172a;
    color: #f8fafc;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    font-size: 16px;
    line-height: 1.42;
  }}
  .slide {{
    position: relative;
    width: 13.333in;
    height: 7.5in;
    padding: 0.42in 0.6in 0.48in 0.6in;
    background: #0f172a;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    justify-content: flex-start;
  }}
  .slide:not(:last-of-type) {{
    page-break-after: always;
    break-after: page;
  }}
  .top-bar {{
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 6px;
    background: linear-gradient(90deg, #ef4444 0%, #38bdf8 50%, #2dd4bf 100%);
  }}
  .title-slide {{
    justify-content: center;
    background: radial-gradient(circle at 80% 20%, #1e293b 0%, #0f172a 70%);
  }}
  .title-content {{
    max-width: 11.5in;
  }}
  .badge {{
    display: inline-block;
    padding: 6px 14px;
    background: #1e293b;
    border: 1px solid #38bdf8;
    color: #38bdf8;
    border-radius: 999px;
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.08em;
    margin-bottom: 20px;
  }}
  .title-slide h1 {{
    font-size: 42px;
    line-height: 1.18;
    margin: 0 0 24px 0;
    color: #f8fafc;
    font-weight: 800;
  }}
  .title-slide .subtitle p {{
    font-size: 19px;
    color: #94a3b8;
    margin: 0 0 28px 0;
    max-width: 10.2in;
    line-height: 1.5;
  }}
  .pill-row {{
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
  }}
  .pill {{
    padding: 8px 16px;
    border-radius: 8px;
    background: #1e293b;
    font-size: 13.5px;
    font-weight: 600;
    border: 1px solid #475569;
  }}
  .pill.blue {{ border-color: #38bdf8; color: #38bdf8; }}
  .pill.teal {{ border-color: #2dd4bf; color: #2dd4bf; }}
  .pill.red {{ border-color: #ef4444; color: #fca5a5; }}
  .pill.purple {{ border-color: #c084fc; color: #d8b4fe; }}
  .pill.gold {{ border-color: #facc15; color: #fde047; }}

  .slide-inner {{
    flex: 1;
    display: flex;
    flex-direction: column;
    justify-content: flex-start;
    overflow: hidden;
  }}
  h1, h2 {{
    font-size: 27px;
    font-weight: 800;
    color: #f8fafc;
    margin: 0 0 12px 0;
    padding-bottom: 8px;
    border-bottom: 1px solid #334155;
  }}
  h3 {{
    font-size: 18px;
    font-weight: 700;
    color: #38bdf8;
    margin: 10px 0 6px 0;
  }}
  p, li {{
    font-size: 14.5px;
    color: #e2e8f0;
  }}
  ul, ol {{
    margin: 4px 0 10px 0;
    padding-left: 24px;
  }}
  li {{
    margin-bottom: 5px;
  }}
  li > ul {{
    margin-top: 4px;
    margin-bottom: 4px;
  }}
  a {{
    color: #38bdf8;
    text-decoration: none;
  }}
  code {{
    font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
    font-size: 0.9em;
    background: #1e293b;
    color: #fde047;
    padding: 2px 6px;
    border-radius: 4px;
  }}
  pre {{
    background: #111827;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 12px 16px;
    margin: 8px 0 12px 0;
    overflow-x: auto;
  }}
  pre code {{
    background: transparent;
    color: #f8fafc;
    padding: 0;
    font-size: 13.5px;
    line-height: 1.45;
  }}
  .mermaid-container {{
    background: #111827;
    border: 1px solid #334155;
    border-radius: 10px;
    padding: 10px 14px;
    margin: 6px 0 12px 0;
    display: flex;
    justify-content: center;
    align-items: center;
    max-height: 4.4in;
    overflow: hidden;
  }}
  .mermaid-container pre.mermaid {{
    border: none;
    background: transparent;
    margin: 0;
    padding: 0;
    width: 100%;
    text-align: center;
  }}
  .mermaid-container svg {{
    max-width: 100% !important;
    max-height: 4.15in !important;
    height: auto !important;
  }}
  .callout {{
    background: rgba(250, 204, 21, 0.08);
    border-left: 4px solid #facc15;
    border-radius: 6px;
    padding: 10px 16px;
    margin-top: 8px;
  }}
  .callout-note {{ background: rgba(56, 189, 248, 0.08); border-left-color: #38bdf8; }}
  .callout-tip {{ background: rgba(45, 212, 191, 0.08); border-left-color: #2dd4bf; }}
  .callout-caution {{ background: rgba(239, 68, 68, 0.08); border-left-color: #ef4444; }}
  .callout-title {{
    font-weight: 700;
    font-size: 13.5px;
    color: #facc15;
    margin-bottom: 4px;
    letter-spacing: 0.03em;
  }}
  .callout-note .callout-title {{ color: #38bdf8; }}
  .callout-tip .callout-title {{ color: #2dd4bf; }}
  .callout-caution .callout-title {{ color: #ef4444; }}
  .callout-body p {{
    margin: 0;
    font-size: 13.8px;
    color: #f8fafc;
  }}
  table {{
    width: 100%;
    border-collapse: collapse;
    margin-top: 6px;
    font-size: 13.2px;
    background: #1e293b;
    border-radius: 8px;
    overflow: hidden;
  }}
  th, td {{
    border: 1px solid #334155;
    padding: 8px 12px;
    text-align: left;
    vertical-align: top;
  }}
  th {{
    background: #0f172a;
    color: #38bdf8;
    font-weight: 700;
    font-size: 13.5px;
  }}
  tr:nth-child(even) td {{
    background: #162032;
  }}
  td:first-child {{
    color: #fde047;
    font-weight: 600;
  }}
  .slide-footer {{
    position: absolute;
    bottom: 0.16in;
    left: 0.6in;
    right: 0.6in;
    display: flex;
    justify-content: space-between;
    font-size: 11.5px;
    color: #64748b;
    border-top: 1px solid #1e293b;
    padding-top: 6px;
  }}
</style>
<script src="https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"></script>
<script>
  mermaid.initialize({{
    startOnLoad: true,
    theme: "dark",
    securityLevel: "loose",
    flowchart: {{ useMaxWidth: true, htmlLabels: true, curve: "basis" }},
    sequence: {{ useMaxWidth: true, mirrorActors: false, messageMargin: 28, boxMargin: 8 }}
  }});
</script>
</head>
<body>
{"".join(slide_sections)}
</body>
</html>
"""


def main():
    parser = argparse.ArgumentParser(
        description="Convert a Markdown slide deck (with <!-- slide --> or --- separators) to a widescreen PDF."
    )
    parser.add_argument(
        "input_md",
        nargs="?",
        default="sf_marimo_slide_deck.md",
        help="Input Markdown slide deck file (default: sf_marimo_slide_deck.md)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Output PDF file path (default: <input_stem>.pdf)",
    )
    parser.add_argument(
        "--html",
        default=None,
        help="Optional path to keep the intermediate HTML file",
    )
    parser.add_argument(
        "--separator",
        default=r"^\s*(?:<!--\s*slide\s*-->|---)\s*$",
        help="Regex pattern separating slides",
    )
    args = parser.parse_args()

    md_path = Path(args.input_md).resolve()
    pdf_path = Path(args.output).resolve() if args.output else md_path.with_suffix(".pdf")
    html_content = build_html_deck(md_path, separator_pattern=args.separator)

    chrome_bin = find_browser_binary()

    if args.html:
        html_path = Path(args.html).resolve()
        html_path.write_text(html_content, encoding="utf-8")
        cmd = [
            chrome_bin,
            "--headless",
            "--disable-gpu",
            "--no-pdf-header-footer",
            "--virtual-time-budget=8000",
            f"--print-to-pdf={pdf_path}",
            html_path.as_uri(),
        ]
        subprocess.run(cmd, check=True)
    else:
        with tempfile.NamedTemporaryFile("w", suffix=".html", encoding="utf-8", delete=False) as tmp:
            tmp.write(html_content)
            tmp_path = Path(tmp.name)
        try:
            cmd = [
                chrome_bin,
                "--headless",
                "--disable-gpu",
                "--no-pdf-header-footer",
                "--virtual-time-budget=8000",
                f"--print-to-pdf={pdf_path}",
                tmp_path.as_uri(),
            ]
            subprocess.run(cmd, check=True)
        finally:
            tmp_path.unlink(missing_ok=True)

    print(f"Exported PDF to {pdf_path} ({pdf_path.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
