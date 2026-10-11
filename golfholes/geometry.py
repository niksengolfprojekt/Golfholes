"""Enkel plan geometri i meter (SWEREF 99 TM, EPSG:3006).

Inga externa beroenden utöver standardbiblioteket, så att koden går att köra
överallt. Punkter är (E, N) i meter.
"""
from __future__ import annotations

import math
from typing import Iterable, Sequence

Point = tuple[float, float]


def dist(a: Point, b: Point) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def polyline_length(line: Sequence[Point]) -> float:
    return sum(dist(line[i], line[i + 1]) for i in range(len(line) - 1))


def point_along(line: Sequence[Point], station: float) -> Point:
    """Punkt på linjen `station` meter från linjens start (klipps mot ändarna)."""
    if station <= 0:
        return tuple(line[0])
    walked = 0.0
    for i in range(len(line) - 1):
        a, b = line[i], line[i + 1]
        seg = dist(a, b)
        if walked + seg >= station:
            t = (station - walked) / seg if seg else 0.0
            return (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))
        walked += seg
    return tuple(line[-1])


def project(line: Sequence[Point], p: Point) -> tuple[float, float]:
    """Projicera punkten på linjen.

    Returnerar (station, sida): station = meter längs linjen till närmaste punkt,
    sida = signerat sidoavstånd i meter (negativt = vänster, positivt = höger,
    sett i spelriktningen).
    """
    best = (math.inf, 0.0, 0.0)  # (avstånd, station, sida)
    walked = 0.0
    for i in range(len(line) - 1):
        a, b = line[i], line[i + 1]
        dx, dy = b[0] - a[0], b[1] - a[1]
        seg2 = dx * dx + dy * dy
        seg = math.sqrt(seg2)
        t = 0.0 if seg2 == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / seg2))
        q = (a[0] + t * dx, a[1] + t * dy)
        d = dist(p, q)
        if d < best[0]:
            cross = dx * (p[1] - a[1]) - dy * (p[0] - a[0])  # >0 = vänster
            side = -d if cross > 0 else d
            best = (d, walked + t * seg, side)
        walked += seg
    return best[1], best[2]


def station_range(line: Sequence[Point], polygon: Iterable[Point]) -> tuple[float, float, float]:
    """Första station, sista station och medelsida för en polygon längs linjen."""
    st, sides = [], []
    for p in polygon:
        s, side = project(line, p)
        st.append(s)
        sides.append(side)
    return min(st), max(st), sum(sides) / len(sides)


def centroid(polygon: Sequence[Point]) -> Point:
    """Ytans tyngdpunkt (shoelace)."""
    a = cx = cy = 0.0
    n = len(polygon)
    for i in range(n):
        x0, y0 = polygon[i]
        x1, y1 = polygon[(i + 1) % n]
        c = x0 * y1 - x1 * y0
        a += c
        cx += (x0 + x1) * c
        cy += (y0 + y1) * c
    if abs(a) < 1e-9:
        xs, ys = zip(*polygon)
        return (sum(xs) / n, sum(ys) / n)
    a *= 0.5
    return (cx / (6 * a), cy / (6 * a))


def contains(polygon: Sequence[Point], p: Point) -> bool:
    """Ligger punkten inuti polygonen (ray casting)."""
    x, y = p
    inside = False
    n = len(polygon)
    for i in range(n):
        x0, y0 = polygon[i]
        x1, y1 = polygon[(i + 1) % n]
        if (y0 > y) != (y1 > y) and x < (x1 - x0) * (y - y0) / (y1 - y0) + x0:
            inside = not inside
    return inside


def rotate(p: Point, origin: Point, degrees_ccw: float) -> Point:
    """Rotera punkten moturs kring origin."""
    r = math.radians(degrees_ccw)
    x, y = p[0] - origin[0], p[1] - origin[1]
    return (x * math.cos(r) - y * math.sin(r), x * math.sin(r) + y * math.cos(r))


def bearing(a: Point, b: Point) -> float:
    """Kompassriktning i grader från a mot b (0 = norr, 90 = öster)."""
    return math.degrees(math.atan2(b[0] - a[0], b[1] - a[1])) % 360
