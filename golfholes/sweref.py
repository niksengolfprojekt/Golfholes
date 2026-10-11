"""WGS84 (lat/lon) → SWEREF 99 TM (EPSG:3006), Gauss–Krüger enligt Lantmäteriet.

Används för att räkna om koordinater från t.ex. OpenStreetMap eller mobil-GPS
till samma system som Lantmäteriets ortofoto och höjdmodell.
"""
from __future__ import annotations

import math

_A = 6378137.0
_F = 1 / 298.257222101  # GRS 80
_LON0 = 15.0
_K0 = 0.9996
_FE = 500000.0


def wgs84_to_sweref99tm(lat: float, lon: float) -> tuple[float, float]:
    """Returnerar (E, N) i meter."""
    e2 = _F * (2 - _F)
    n = _F / (2 - _F)
    a_hat = _A / (1 + n) * (1 + n**2 / 4 + n**4 / 64)
    beta = [
        n / 2 - 2 * n**2 / 3 + 5 * n**3 / 16 + 41 * n**4 / 180,
        13 * n**2 / 48 - 3 * n**3 / 5 + 557 * n**4 / 1440,
        61 * n**3 / 240 - 103 * n**4 / 140,
        49561 * n**4 / 161280,
    ]
    phi = math.radians(lat)
    lam = math.radians(lon - _LON0)
    s = math.sin(phi)
    phi_star = phi - s * math.cos(phi) * (
        e2
        + (5 * e2**2 - e2**3) / 6 * s**2
        + (104 * e2**3 - 45 * e2**4) / 120 * s**4
        + 1237 * e2**4 / 1260 * s**6
    )
    xi = math.atan(math.tan(phi_star) / math.cos(lam))
    eta = math.atanh(math.cos(phi_star) * math.sin(lam))
    x = _K0 * a_hat * (xi + sum(b * math.sin(2 * (i + 1) * xi) * math.cosh(2 * (i + 1) * eta) for i, b in enumerate(beta)))
    y = _K0 * a_hat * (eta + sum(b * math.cos(2 * (i + 1) * xi) * math.sinh(2 * (i + 1) * eta) for i, b in enumerate(beta))) + _FE
    return y, x
