"""构图原语：把派生点的语义算成坐标，并给出对应的 GeoGebra 表达式。

模型只负责说“D 是 AB 的中点”，坐标由这里算，避免它随手写出一个看着像的坐标；
同时生成依赖式，拖动顶点时图形不会散。
"""

from __future__ import annotations

import math
from typing import Callable

Vec = tuple[float, float]


# ------------------------------------------------------------------ 向量小工具


def _sub(a: Vec, b: Vec) -> Vec:
    return (a[0] - b[0], a[1] - b[1])


def _add(a: Vec, b: Vec) -> Vec:
    return (a[0] + b[0], a[1] + b[1])


def _mul(a: Vec, k: float) -> Vec:
    return (a[0] * k, a[1] * k)


def _dot(a: Vec, b: Vec) -> float:
    return a[0] * b[0] + a[1] * b[1]


def _cross(a: Vec, b: Vec) -> float:
    return a[0] * b[1] - a[1] * b[0]


def _dist(a: Vec, b: Vec) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _unit(a: Vec) -> Vec:
    n = math.hypot(*a)
    if n < 1e-12:
        return (0.0, 0.0)
    return (a[0] / n, a[1] / n)


# ------------------------------------------------------------------ 几何计算


def line_intersection(p1: Vec, p2: Vec, p3: Vec, p4: Vec) -> Vec | None:
    """两直线交点（含延长线）；平行返回 None。"""
    d1 = _sub(p2, p1)
    d2 = _sub(p4, p3)
    den = _cross(d1, d2)
    if abs(den) < 1e-12:
        return None
    t = _cross(_sub(p3, p1), d2) / den
    return _add(p1, _mul(d1, t))


def closest_on_line(p: Vec, a: Vec, b: Vec) -> Vec:
    """p 到直线 ab 的垂足。"""
    d = _sub(b, a)
    den = _dot(d, d)
    if den < 1e-12:
        return a
    t = _dot(_sub(p, a), d) / den
    return _add(a, _mul(d, t))


def circle_line_intersection(c: Vec, r: float, a: Vec, b: Vec) -> list[Vec]:
    """直线 ab 与圆 (c,r) 的交点（0~2 个）。"""
    d = _sub(b, a)
    den = _dot(d, d)
    if den < 1e-12:
        return []
    t0 = _dot(_sub(c, a), d) / den
    foot = _add(a, _mul(d, t0))
    h2 = r * r - _dot(_sub(foot, c), _sub(foot, c))
    if h2 < -1e-9:
        return []
    if abs(h2) < 1e-9:
        return [foot]
    h = math.sqrt(max(h2, 0.0))
    u = _unit(d)
    return [_sub(foot, _mul(u, h)), _add(foot, _mul(u, h))]


def circle_circle_intersection(c1: Vec, r1: float, c2: Vec, r2: float) -> list[Vec]:
    d = _dist(c1, c2)
    if d < 1e-12 or d > r1 + r2 + 1e-9 or d < abs(r1 - r2) - 1e-9:
        return []
    a = (r1 * r1 - r2 * r2 + d * d) / (2 * d)
    h2 = r1 * r1 - a * a
    if h2 < -1e-9:
        return []
    h = math.sqrt(max(h2, 0.0))
    u = _unit(_sub(c2, c1))
    p = _add(c1, _mul(u, a))
    n = (-u[1], u[0])
    if h < 1e-9:
        return [p]
    return [_add(p, _mul(n, h)), _sub(p, _mul(n, h))]


# ------------------------------------------------------------------ 原语


def _num(v) -> float:
    return float(v)


def _pt(args: list, pts: dict[str, Vec]) -> Vec:
    name = args[0]
    if isinstance(name, str) and name in pts:
        return pts[name]
    raise KeyError(f"未知的点 {name}")


def c_midpoint(args: list, pts: dict[str, Vec]) -> Vec:
    a, b = _pt(args, pts), _pt(args[1:], pts)
    return ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)


def c_on_segment(args: list, pts: dict[str, Vec]) -> Vec:
    a, b = _pt(args, pts), _pt(args[1:], pts)
    t = args[2]
    if isinstance(t, str):
        if ":" in t:
            x, y = t.split(":", 1)
            t = float(x) / (float(x) + float(y))
        else:
            t = float(t)
    t = float(t)
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def c_foot(args: list, pts: dict[str, Vec]) -> Vec:
    p, a, b = _pt(args, pts), _pt(args[1:], pts), _pt(args[2:], pts)
    return closest_on_line(p, a, b)


def c_intersect(args: list, pts: dict[str, Vec]) -> Vec | None:
    p1, p2 = _pt(args, pts), _pt(args[1:], pts)
    p3, p4 = _pt(args[2:], pts), _pt(args[3:], pts)
    return line_intersection(p1, p2, p3, p4)


def c_bisector_foot(args: list, pts: dict[str, Vec]) -> Vec:
    """∠C 的角平分线与 AB 的交点：AD/DB = CA/CB。"""
    c, a, b = _pt(args, pts), _pt(args[1:], pts), _pt(args[2:], pts)
    ca, cb = _dist(c, a), _dist(c, b)
    if ca + cb < 1e-12:
        return ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
    t = ca / (ca + cb)
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def c_centroid(args: list, pts: dict[str, Vec]) -> Vec:
    a, b, c = _pt(args, pts), _pt(args[1:], pts), _pt(args[2:], pts)
    return ((a[0] + b[0] + c[0]) / 3, (a[1] + b[1] + c[1]) / 3)


def c_circumcenter(args: list, pts: dict[str, Vec]) -> Vec | None:
    a, b, c = _pt(args, pts), _pt(args[1:], pts), _pt(args[2:], pts)
    d = 2 * (a[0] * (b[1] - c[1]) + b[0] * (c[1] - a[1]) + c[0] * (a[1] - b[1]))
    if abs(d) < 1e-12:
        return None
    a2, b2, c2 = a[0] ** 2 + a[1] ** 2, b[0] ** 2 + b[1] ** 2, c[0] ** 2 + c[1] ** 2
    ux = (a2 * (b[1] - c[1]) + b2 * (c[1] - a[1]) + c2 * (a[1] - b[1])) / d
    uy = (a2 * (c[0] - b[0]) + b2 * (a[0] - c[0]) + c2 * (b[0] - a[0])) / d
    return (ux, uy)


def c_incenter(args: list, pts: dict[str, Vec]) -> Vec:
    a, b, c = _pt(args, pts), _pt(args[1:], pts), _pt(args[2:], pts)
    la, lb, lc = _dist(b, c), _dist(a, c), _dist(a, b)
    s = la + lb + lc
    if s < 1e-12:
        return a
    return ((la * a[0] + lb * b[0] + lc * c[0]) / s, (la * a[1] + lb * b[1] + lc * c[1]) / s)


def c_orthocenter(args: list, pts: dict[str, Vec]) -> Vec | None:
    a, b, c = _pt(args, pts), _pt(args[1:], pts), _pt(args[2:], pts)
    h1 = closest_on_line(a, b, c)          # A 到 BC 的垂足
    h2 = closest_on_line(b, a, c)          # B 到 AC 的垂足
    return line_intersection(a, h1, b, h2)


def c_rotate(args: list, pts: dict[str, Vec]) -> Vec:
    p, center = _pt(args, pts), _pt(args[1:], pts)
    deg = _num(args[2])
    th = math.radians(deg)
    dx, dy = p[0] - center[0], p[1] - center[1]
    return (
        center[0] + dx * math.cos(th) - dy * math.sin(th),
        center[1] + dx * math.sin(th) + dy * math.cos(th),
    )


def c_reflect(args: list, pts: dict[str, Vec]) -> Vec:
    p, a, b = _pt(args, pts), _pt(args[1:], pts), _pt(args[2:], pts)
    f = closest_on_line(p, a, b)
    return (2 * f[0] - p[0], 2 * f[1] - p[1])


def c_translate(args: list, pts: dict[str, Vec]) -> Vec:
    p, a, b = _pt(args, pts), _pt(args[1:], pts), _pt(args[2:], pts)
    return (p[0] + (b[0] - a[0]), p[1] + (b[1] - a[1]))


def c_line_circle(args: list, pts: dict[str, Vec]) -> Vec | None:
    """直线 AB 与圆的交点：args = [A, B, O, R, which?]，R 可以是数字或圆上的点。"""
    a, b, o = _pt(args, pts), _pt(args[1:], pts), _pt(args[2:], pts)
    r = _radius(args[3], o, pts)
    which = int(args[4]) if len(args) > 4 else 0
    cand = circle_line_intersection(o, r, a, b)
    if not cand:
        return None
    return cand[min(max(which, 0), len(cand) - 1)]


def c_circle_circle(args: list, pts: dict[str, Vec]) -> Vec | None:
    """两圆交点：args = [O1, R1, O2, R2, which?]。"""
    o1 = _pt(args, pts)
    r1 = _radius(args[1], o1, pts)
    o2 = _pt(args[2:], pts)
    r2 = _radius(args[3], o2, pts)
    which = int(args[4]) if len(args) > 4 else 0
    cand = circle_circle_intersection(o1, r1, o2, r2)
    if not cand:
        return None
    return cand[min(max(which, 0), len(cand) - 1)]


def c_slope_point(args: list, pts: dict[str, Vec]) -> Vec:
    """过 P、斜率为 k 的直线上的一点（P 往右 1 个单位），用来确定一条直线。"""
    p = _pt(args, pts)
    k = _num(args[1])
    return (p[0] + 1.0, p[1] + k)


def c_point_at(args: list, pts: dict[str, Vec]) -> Vec:
    p = _pt(args, pts)
    return (p[0] + _num(args[1]), p[1] + _num(args[2]))


def _radius(arg, center: Vec, pts: dict[str, Vec]) -> float:
    """半径参数既可以是数字，也可以是圆上的点。"""
    if isinstance(arg, str) and arg in pts:
        return _dist(center, pts[arg])
    return float(arg)



# ------------------------------------------------------------------ 注册表

PRIMS: dict[str, Callable[[list, dict], Vec | None]] = {
    "midpoint": c_midpoint,
    "on_segment": c_on_segment,
    "foot": c_foot,
    "perpendicular_foot": c_foot,
    "intersect": c_intersect,
    "intersection": c_intersect,
    "bisector_foot": c_bisector_foot,
    "angle_bisector_foot": c_bisector_foot,
    "centroid": c_centroid,
    "circumcenter": c_circumcenter,
    "incenter": c_incenter,
    "orthocenter": c_orthocenter,
    "rotate": c_rotate,
    "reflect": c_reflect,
    "translate": c_translate,
    "line_circle": c_line_circle,
    "circle_circle": c_circle_circle,
    "slope_point": c_slope_point,
    "point_at": c_point_at,
}

# GeoGebra 依赖式（拖动起点时仍然成立）
GGB: dict[str, Callable[[list], str]] = {
    "midpoint": lambda a: f"Midpoint({a[0]},{a[1]})",
    "on_segment": lambda a: f"Point(Segment({a[0]},{a[1]}),{a[2]})",
    "foot": lambda a: f"ClosestPoint(Line({a[1]},{a[2]}),{a[0]})",
    "intersect": lambda a: f"Intersect(Line({a[0]},{a[1]}),Line({a[2]},{a[3]}))",
    "bisector_foot": lambda a: f"Intersect(Line({a[1]},{a[2]}),AngleBisector({a[1]},{a[0]},{a[2]}))",
    "centroid": lambda a: f"Intersect(Line({a[0]},Midpoint({a[1]},{a[2]})),Line({a[1]},Midpoint({a[0]},{a[2]})))",
    "circumcenter": lambda a: f"Intersect(PerpendicularBisector({a[0]},{a[1]}),PerpendicularBisector({a[1]},{a[2]}))",
    "incenter": lambda a: f"Intersect(AngleBisector({a[0]},{a[1]},{a[2]}),AngleBisector({a[1]},{a[0]},{a[2]}))",
    "orthocenter": lambda a: f"Intersect(PerpendicularLine({a[0]},Line({a[1]},{a[2]})),PerpendicularLine({a[1]},Line({a[0]},{a[2]})))",
    "rotate": lambda a: f"Rotate({a[0]},{a[2]}°,{a[1]})",
    "reflect": lambda a: f"Reflect({a[0]},Line({a[1]},{a[2]}))",
    "translate": lambda a: f"Translate({a[0]},Vector({a[1]},{a[2]}))",
    "line_circle": lambda a: (
        f"Intersect(Line({a[0]},{a[1]}),Circle({a[2]},{a[3]}),{int(a[4]) + 1 if len(a) > 4 else 1})"
    ),
    "circle_circle": lambda a: (
        f"Intersect(Circle({a[0]},{a[1]}),Circle({a[2]},{a[3]}),{int(a[4]) + 1 if len(a) > 4 else 1})"
    ),
}

ALIASES = {
    "perpendicular_foot": "foot",
    "intersection": "intersect",
    "angle_bisector_foot": "bisector_foot",
}


def canonical(kind: str) -> str:
    k = (kind or "").strip().lower().replace("-", "_").replace(" ", "_")
    return ALIASES.get(k, k)


def evaluate(kind: str, args: list, pts: dict[str, Vec]) -> Vec | None:
    fn = PRIMS.get(canonical(kind))
    if fn is None:
        raise KeyError(f"不认识的构造 {kind}")
    return fn(args, pts)


def ggb_expr(kind: str, args: list) -> str | None:
    fn = GGB.get(canonical(kind))
    if fn is None:
        return None
    try:
        return fn(args)
    except Exception:
        return None


def topo_order(specs: list[dict]) -> list[dict]:
    """按依赖排序：先自由点，再依赖别点的派生点。"""
    free = [s for s in specs if s.get("x") is not None and s.get("y") is not None and not s.get("construct")]
    derived = [s for s in specs if s not in free]
    out = list(free)
    pending = list(derived)
    known = {s["name"] for s in free}
    for _ in range(len(pending) + 1):
        if not pending:
            break
        rest = []
        for s in pending:
            deps = [a for a in (s.get("args") or []) if isinstance(a, str) and a in {p["name"] for p in specs}]
            if all(d in known for d in deps):
                out.append(s)
                known.add(s["name"])
            else:
                rest.append(s)
        pending = rest
    out.extend(pending)  # 有环或依赖缺失的，留在最后，由调用方报错
    return out
