"""QR-koder som SVG.

Använder biblioteket `segno` om det finns (installeras på Macen). Annars ritas en
tydligt markerad platshållare, så att ingen trycker en skylt med en falsk kod.
"""
from __future__ import annotations

import io


def qr_svg(url: str) -> tuple[str, bool]:
    """Returnerar (svg, äkta). äkta=False betyder platshållare."""
    try:
        import segno  # type: ignore
    except ImportError:
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
            '<rect x="1" y="1" width="98" height="98" fill="#fff" stroke="#c0473b" stroke-width="2" stroke-dasharray="6 4"/>'
            '<text x="50" y="44" text-anchor="middle" font-family="Inter, Arial" font-size="11" fill="#c0473b" font-weight="700">QR-KOD</text>'
            '<text x="50" y="60" text-anchor="middle" font-family="Inter, Arial" font-size="7" fill="#c0473b">skapas på Macen</text>'
            "</svg>"
        )
        return svg, False
    buf = io.BytesIO()
    segno.make(url, error="m").save(buf, kind="svg", border=0, dark="#2f3a2d", xmldecl=False, svgns=True, nl=False)
    svg = buf.getvalue().decode("utf-8")
    return svg, True
