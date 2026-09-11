#!/usr/bin/env python3
"""Render a docs/*.html page to PDF.

    uv run python tools/make_pdf.py docs/introduction.html

Chrome's headless print, rather than a PDF library. It is already on any
machine that can look at the HTML, it renders the page exactly as the browser
does -- so the HTML stays the single source and the PDF cannot drift from it --
and it emits real selectable text rather than an image. The alternative was a
new dependency (weasyprint, reportlab) that would render the CSS a second,
slightly different way.

Finds Chrome by trying the usual command names. If none is installed, say so
and name the remedy rather than failing on a bare FileNotFoundError.
"""

import argparse
import shutil
import subprocess
from pathlib import Path

# Debian/Ubuntu, Arch, Fedora and macOS spell it differently; the snap and the
# .deb also differ. Ordered so a real Chrome wins over a symlink to one.
_CHROME_NAMES = (
    "google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
)


def find_chrome() -> str:
    for name in _CHROME_NAMES:
        found = shutil.which(name) or (name if Path(name).exists() else None)
        if found:
            return found
    raise SystemExit(
        "no Chrome or Chromium found, and this renders the PDF with Chrome's "
        "own print engine so the PDF cannot drift from the page.\n"
        "Install one (apt install chromium, brew install --cask google-chrome), "
        "or open the HTML in any browser and print to PDF by hand -- the page "
        "carries its own @page rules, so the result is the same."
    )


def render(html: Path, pdf: Path) -> None:
    chrome = find_chrome()
    pdf.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [chrome, "--headless", "--disable-gpu", "--no-sandbox",
         # Chrome's own header and footer are a URL and a date stamped into
         # every margin. The page sets its own; these would be noise on a
         # document meant to be handed to someone.
         "--no-pdf-header-footer",
         f"--print-to-pdf={pdf}", html.resolve().as_uri()],
        capture_output=True, text=True, timeout=180,
    )
    # Chrome exits 0 and writes nothing when it cannot reach the page, so the
    # exit code alone is not evidence that a PDF exists.
    if not pdf.exists() or pdf.stat().st_size == 0:
        raise SystemExit(
            f"chrome produced no PDF for {html}\n{result.stderr.strip()[:800]}")
    print(f"[pdf] {html} -> {pdf}  ({pdf.stat().st_size / 1024:.0f} KB)")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Render a docs/*.html page to PDF.")
    parser.add_argument("html", type=Path, help="the page to render")
    parser.add_argument("-o", "--out", type=Path,
                        help="output path (default: alongside, named for the "
                             "project and the page)")
    args = parser.parse_args()

    if not args.html.exists():
        raise SystemExit(f"no such page: {args.html}")
    out = args.out or args.html.with_name(f"cidoc-crm-mcp-{args.html.stem}.pdf")
    render(args.html, out)


if __name__ == "__main__":
    main()
