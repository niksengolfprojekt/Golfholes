"""Gör PNG och PDF av SVG/HTML med Chromium (Playwright).

Kräver `pip install playwright` och `playwright install chromium` på Macen.
"""
from __future__ import annotations

from pathlib import Path


def _page_html(svg_or_html: str) -> str:
    if svg_or_html.lstrip().startswith("<!doctype") or svg_or_html.lstrip().startswith("<html"):
        return svg_or_html
    return f"<!doctype html><html><head><meta charset='utf-8'><style>html,body{{margin:0;padding:0}}svg{{display:block}}</style></head><body>{svg_or_html}</body></html>"


def to_png(svg_or_html: str, out: str | Path, width_px: int, height_px: int, scale: float = 2.0) -> Path:
    from playwright.sync_api import sync_playwright

    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={"width": int(width_px), "height": int(height_px)}, device_scale_factor=scale)
        page.set_content(_page_html(svg_or_html), wait_until="networkidle")
        page.screenshot(path=str(out), full_page=True)
        b.close()
    return out


def to_pdf(html: str, out: str | Path, width_mm: float, height_mm: float) -> Path:
    from playwright.sync_api import sync_playwright

    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page()
        page.set_content(_page_html(html), wait_until="networkidle")
        page.pdf(path=str(out), width=f"{width_mm}mm", height=f"{height_mm}mm", print_background=True,
                 margin={"top": "0", "right": "0", "bottom": "0", "left": "0"})
        b.close()
    return out
