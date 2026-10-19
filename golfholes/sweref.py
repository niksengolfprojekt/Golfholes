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


def sweref99tm_to_wgs84(e: float, n: float) -> tuple[float, float]:
    """Returnerar (lat, lon) i grader. Omvändningen av wgs84_to_sweref99tm."""
    e2 = _F * (2 - _F)
    nn = _F / (2 - _F)
    a_hat = _A / (1 + nn) * (1 + nn**2 / 4 + nn**4 / 64)
    delta = [
        nn / 2 - 2 * nn**2 / 3 + 37 * nn**3 / 96 - nn**4 / 360,
        nn**2 / 48 + nn**3 / 15 - 437 * nn**4 / 1440,
        17 * nn**3 / 480 - 37 * nn**4 / 840,
        4397 * nn**4 / 161280,
    ]
    xi = n / (_K0 * a_hat)
    eta = (e - _FE) / (_K0 * a_hat)
    xi_p = xi - sum(d * math.sin(2 * (i + 1) * xi) * math.cosh(2 * (i + 1) * eta) for i, d in enumerate(delta))
    eta_p = eta - sum(d * math.cos(2 * (i + 1) * xi) * math.sinh(2 * (i + 1) * eta) for i, d in enumerate(delta))
    phi_star = math.asin(math.sin(xi_p) / math.cosh(eta_p))
    lam = math.atan(math.sinh(eta_p) / math.cos(xi_p))
    a_ = e2 + e2**2 + e2**3 + e2**4
    b_ = -(7 * e2**2 + 17 * e2**3 + 30 * e2**4) / 6
    c_ = (224 * e2**3 + 889 * e2**4) / 120
    d_ = -4279 * e2**4 / 1260
    s, c = math.sin(phi_star), math.cos(phi_star)
    phi = phi_star + s * c * (a_ + b_ * s**2 + c_ * s**4 + d_ * s**6)
    return math.degrees(phi), _LON0 + math.degrees(lam)
