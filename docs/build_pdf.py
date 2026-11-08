"""Render docs/solution.html -> docs/solution.pdf (A4) with headless Chromium, and report page count."""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

src = Path(__file__).parent / "solution.html"
dst = Path(__file__).parent / "solution.pdf"
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page()
    pg.goto(src.resolve().as_uri())
    pg.pdf(path=str(dst), format="A4", print_background=True,
           margin={"top": "11mm", "bottom": "11mm", "left": "13mm", "right": "13mm"})
    if len(sys.argv) > 1:
        pg.set_viewport_size({"width": 794, "height": 1123})
        pg.screenshot(path=sys.argv[1], full_page=True)
    b.close()
from pypdf import PdfReader  # noqa: E402
print("pages:", len(PdfReader(str(dst)).pages))
