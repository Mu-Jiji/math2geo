"""把模型返回的作图方案 JSON 转成 Scene。

方案只说“有哪些点、谁由谁派生、哪些线要画、题设给了什么条件”，
具体坐标由 construct.py 算，这样模型估错坐标也不会把图带偏。
"""

from __future__ import annotations

import math
from typing import Any

from . import construct
from .model import (
    AngleMark,
    CircleObj,
    FuncObj,
    LineObj,
    ParamObj,
    PointObj,
    PolygonObj,
    RefLineObj,
    Scene,
    SegmentObj,
    SolutionStep,
    TextObj,
)

PALETTE = {
    "vertex": "#1a1a1a",
    "derived": "#1a1a1a",
    "auxiliary": "#868e96",
    "center": "#1c7ed6",
}


class PlanError(ValueError):
    """方案结构不合法。"""


# ------------------------------------------------------------------ 小工具


def _f(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _name(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _as_pair(item: Any) -> tuple[str, str] | None:
    """线段/直线的两种写法：[A,B] 或 {a:A,b:B}。"""
    if isinstance(item, (list, tuple)) and len(item) >= 2:
        return _name(item[0]), _name(item[1])
    if isinstance(item, dict):
        a = item.get("a") or item.get("from") or item.get("p1")
        b = item.get("b") or item.get("to") or item.get("p2")
        if a and b:
            return _name(a), _name(b)
    return None


def _angle(a: tuple[float, float], v: tuple[float, float], b: tuple[float, float]) -> float:
    v1 = (a[0] - v[0], a[1] - v[1])
    v2 = (b[0] - v[0], b[1] - v[1])
    n1 = math.hypot(*v1) or 1.0
    n2 = math.hypot(*v2) or 1.0
    c = max(-1.0, min(1.0, (v1[0] * v2[0] + v1[1] * v2[1]) / (n1 * n2)))
    return math.degrees(math.acos(c))


# ------------------------------------------------------------------ 主流程


def build_scene(plan: dict[str, Any], problem_text: str = "") -> Scene:
    if not isinstance(plan, dict):
        raise PlanError("方案不是 JSON 对象")

    scene = Scene()
    scene.problem_text = str(plan.get("problem_text") or problem_text or "").strip()
    scene.meta["kind"] = plan.get("kind") or "plane_geometry"
    scene.meta["understanding"] = plan.get("understanding") or ""
    scene.meta["answer"] = plan.get("answer") or ""
    scene.meta["source"] = "ai"
    if plan.get("difficulty") is not None:
        try:
            scene.meta["difficulty"] = max(0.0, min(1.0, float(plan["difficulty"])))
        except (TypeError, ValueError):
            pass
    if plan.get("breakthrough"):
        scene.meta["breakthrough"] = str(plan["breakthrough"])

    for w in plan.get("warnings") or []:
        if w:
            scene.warnings.append(str(w))

    _build_points(scene, plan.get("points") or [])
    _build_params(scene, plan.get("params") or [])
    _build_segments(scene, plan.get("segments") or [], role="side")
    _build_segments(scene, plan.get("lines") or [], role="aux", dashed=True)
    _build_circles(scene, plan.get("circles") or [])
    _build_polygons(scene, plan.get("polygons") or [])
    _build_angles(scene, plan.get("angles") or [])
    _build_texts(scene, plan.get("texts") or plan.get("labels") or [])
    _build_funcs(scene, plan.get("functions") or [])
    _build_reflines(scene, plan.get("ref_lines") or [])
    _build_steps(scene, plan.get("steps") or [])
    _run_checks(scene, plan.get("checks") or [])

    view = plan.get("view")
    if isinstance(view, (list, tuple)) and len(view) == 4:
        try:
            scene.meta["view"] = [float(v) for v in view]
        except (TypeError, ValueError):
            pass
    return scene


def _build_points(scene: Scene, specs: list[Any]) -> None:
    norm: list[dict] = []
    for raw in specs:
        if not isinstance(raw, dict):
            continue
        name = _name(raw.get("name") or raw.get("label"))
        if not name:
            continue
        kind = construct.canonical(raw.get("construct") or raw.get("type") or "")
        args = raw.get("args") or raw.get("of") or []
        if not isinstance(args, list):
            args = [args]
        # 用来确定直线的辅助点（slope_point / point_at）默认不显示
        default_role = "auxiliary" if kind in ("slope_point", "point_at") else ("derived" if kind else "vertex")
        show = raw.get("show_label")
        if show is None:
            lab = raw.get("label")
            show = lab if isinstance(lab, bool) else True
        norm.append(
            {
                "name": name,
                "x": raw.get("x"),
                "y": raw.get("y"),
                "z": raw.get("z", 0.0),
                "construct": kind or None,
                "args": args,
                "role": raw.get("role") or default_role,
                "label": bool(show),
                "note": raw.get("note") or "",
                "color": raw.get("color"),
            }
        )

    named = {p["name"] for p in norm}
    pts: dict[str, tuple[float, float]] = {}

    for spec in construct.topo_order(norm):
        name = spec["name"]
        role = str(spec["role"] or "vertex")
        color = spec["color"] or PALETTE.get(role, PALETTE["vertex"])

        z = 0.0
        if spec["construct"]:
            kind = spec["construct"]
            args = [a for a in spec["args"]]
            if kind not in construct.PRIMS:
                scene.warnings.append(f"不认识的构造 {kind}（点 {name} 已跳过）")
                continue
            try:
                xy = construct.evaluate(kind, args, pts)
            except Exception as exc:  # noqa: BLE001 - 方案来自模型，任何异常都不能炸整条流水线
                scene.warnings.append(f"点 {name} 的构造失败（{kind}）：{exc}")
                continue
            if xy is None:
                scene.warnings.append(f"点 {name} 的构造退化（{kind} {args}）")
                continue
            x, y = float(xy[0]), float(xy[1])
            dynamic = construct.ggb_expr(kind, args)
            if dynamic and any(isinstance(a, str) and a not in named for a in args):
                dynamic = None
        else:
            if spec["x"] is None or spec["y"] is None:
                scene.warnings.append(f"点 {name} 既没有坐标也没有构造方式，已跳过")
                continue
            x, y = _f(spec["x"]), _f(spec["y"])
            z = _f(spec.get("z", 0.0))
            dynamic = None

        if not (math.isfinite(x) and math.isfinite(y)):
            scene.warnings.append(f"点 {name} 的坐标不是有限数，已跳过")
            continue

        pts[name] = (x, y)
        scene.points.append(
            PointObj(
                label=name,
                x=x,
                y=y,
                z=z,
                dynamic=dynamic,
                show_label=bool(spec["label"]) and role != "auxiliary",
                color=color,
                role="center" if role == "center" else ("auxiliary" if role == "auxiliary" else ("derived" if dynamic or role == "derived" else role)),
                note=spec["note"],
            )
        )


def _build_segments(scene: Scene, items: list[Any], role: str, dashed: bool | None = None) -> None:
    for raw in items:
        pair = _as_pair(raw)
        if pair is None:
            continue
        a, b = pair
        if not (scene.has(a) and scene.has(b)):
            scene.warnings.append(f"线段 {a}{b} 的端点不存在，已跳过")
            continue
        opts = raw if isinstance(raw, dict) else {}
        is_dashed = opts.get("dashed", dashed)
        obj = (
            SegmentObj(a=a, b=b, role=str(opts.get("role") or role), dashed=bool(is_dashed))
            if role == "side"
            else LineObj(a=a, b=b, role=str(opts.get("role") or role), dashed=bool(True if is_dashed is None else is_dashed))
        )
        if opts.get("color"):
            obj.color = str(opts["color"])
        if role == "side":
            scene.segments.append(obj)  # type: ignore[arg-type]
        else:
            scene.lines.append(obj)  # type: ignore[arg-type]


def _build_circles(scene: Scene, items: list[Any]) -> None:
    for raw in items:
        if not isinstance(raw, dict):
            continue
        color = raw.get("color")
        center = _name(raw.get("center"))
        through = _name(raw.get("through") or raw.get("point"))
        radius = raw.get("radius")

        if not center and isinstance(raw.get("through"), list) and len(raw["through"]) >= 3:
            names = [_name(n) for n in raw["through"][:3]]
            if all(scene.has(n) for n in names):
                coords = {n: scene.coord(n) for n in names}
                c = construct.c_circumcenter(names, coords)
                if c is None:
                    scene.warnings.append(f"圆 {names} 共线，无法确定圆心")
                    continue
                center = "O"
                if scene.has(center):
                    center = "O2"
                scene.points.append(
                    PointObj(label=center, x=c[0], y=c[1], role="center", color=PALETTE["center"], note="外心")
                )
                radius = math.hypot(coords[names[0]][0] - c[0], coords[names[0]][1] - c[1])
                through = names[0]

        if not center or not scene.has(center):
            scene.warnings.append(f"圆 {raw} 缺少有效圆心，已跳过")
            continue

        obj = CircleObj(center=center, color=color)
        if radius is not None:
            obj.radius = _f(radius)
            obj.through = None
        elif through and scene.has(through):
            obj.through = through
        else:
            scene.warnings.append(f"圆 {center} 既没有半径也没有过点，已跳过")
            continue
        scene.circles.append(obj)


def _build_polygons(scene: Scene, items: list[Any]) -> None:
    for raw in items:
        names = raw.get("points") if isinstance(raw, dict) else raw
        if not isinstance(names, list) or len(names) < 3:
            continue
        names = [_name(n) for n in names]
        if not all(scene.has(n) for n in names):
            scene.warnings.append(f"多边形 {names} 有点不存在，已跳过")
            continue
        opts = raw if isinstance(raw, dict) else {}
        scene.polygons.append(
            PolygonObj(points=names, fill=bool(opts.get("fill", False)), color=opts.get("color"))
        )


def _build_angles(scene: Scene, items: list[Any]) -> None:
    for raw in items:
        if not isinstance(raw, dict):
            continue
        vertex = _name(raw.get("vertex") or raw.get("v"))
        a = _name(raw.get("a") or raw.get("p1"))
        b = _name(raw.get("b") or raw.get("p2"))
        if not all(scene.has(n) for n in (a, vertex, b) if n):
            continue
        if not (vertex and a and b):
            continue
        scene.angles.append(
            AngleMark(a=a, vertex=vertex, b=b, label=raw.get("label"), color=raw.get("color"))
        )


def _build_texts(scene: Scene, items: list[Any]) -> None:
    # 点名已经由 matplotlib/GeoGebra 自动标注，方案里重复写一遍会重影
    labels = {p.label for p in scene.points}
    for raw in items:
        if not isinstance(raw, dict) or not raw.get("text"):
            continue
        text = str(raw["text"]).strip()
        if text in labels:
            continue
        scene.texts.append(
            TextObj(
                text=text,
                x=_f(raw.get("x")),
                y=_f(raw.get("y")),
                size=_f(raw.get("size"), 13.0),
                color=raw.get("color"),
            )
        )


def _build_funcs(scene: Scene, items: list[Any]) -> None:
    for raw in items:
        if not isinstance(raw, dict) or not raw.get("expr"):
            continue
        name = _name(raw.get("name") or "f")
        expr = str(raw["expr"]).replace("**", "^")
        scene.funcs.append(
            FuncObj(
                name=name,
                expr=expr,
                xmin=_f(raw.get("xmin"), -6.0),
                xmax=_f(raw.get("xmax"), 6.0),
                color=raw.get("color"),
                role=str(raw.get("role") or "function"),
                dashed=bool(raw.get("dashed", False)),
                label=raw.get("label"),
            )
        )
        # 表达式里出现但没声明的参数（如 a），自动补一条滑动条，否则 GeoGebra 会报“未定义”
        try:
            from . import algebra

            sym = algebra.to_sympy(expr)
            if sym is None:
                continue
            known = {p.name for p in scene.params}
            for name_ in algebra.params_of(sym):
                if name_ not in known and len(name_) <= 2:
                    scene.params.append(ParamObj(name=name_, value=1.0))
                    known.add(name_)
                    scene.warnings.append(f"表达式里有参数 {name_}，已自动加一条滑动条（默认 1）")
        except Exception:
            pass


def _build_params(scene: Scene, items: list[Any]) -> None:
    for raw in items:
        if not isinstance(raw, dict) or not raw.get("name"):
            continue
        scene.params.append(
            ParamObj(
                name=_name(raw["name"]),
                value=_f(raw.get("value"), 1.0),
                min=_f(raw.get("min"), -5.0),
                max=_f(raw.get("max"), 5.0),
                step=_f(raw.get("step"), 0.1),
            )
        )


def _build_reflines(scene: Scene, items: list[Any]) -> None:
    for raw in items:
        if not isinstance(raw, dict):
            continue
        kind = str(raw.get("kind") or "").lower()[:1]
        if kind not in ("h", "v"):
            continue
        scene.ref_lines.append(
            RefLineObj(kind=kind, value=_f(raw.get("value")), label=str(raw.get("label") or ""))
        )


def _build_steps(scene: Scene, items: list[Any]) -> None:
    for raw in items:
        if isinstance(raw, str):
            scene.steps.append(SolutionStep(title=raw))
            continue
        if not isinstance(raw, dict):
            continue
        title = str(raw.get("title") or raw.get("step") or "").strip()
        if not title:
            continue
        scene.steps.append(SolutionStep(title=title, body=str(raw.get("body") or raw.get("detail") or "")))


def _run_checks(scene: Scene, items: list[Any]) -> None:
    """核对题设给出的量，结果写进 meta['checks']，不一致时给警告。"""
    results: list[dict] = []
    for raw in items:
        if not isinstance(raw, dict):
            continue
        kind = str(raw.get("type") or "").lower()
        target = raw.get("value")
        ok = None
        got = 0.0
        want = 0.0
        what = ""

        if kind in ("length", "distance", "len"):
            pair = raw.get("of") or raw.get("points") or raw.get("args") or []
            if not (isinstance(pair, list) and len(pair) >= 2) or target is None:
                continue
            a, b = _name(pair[0]), _name(pair[1])
            if not (scene.has(a) and scene.has(b)):
                continue
            got = math.dist(scene.coord(a), scene.coord(b))
            want = _f(target)
            ok = abs(got - want) <= max(1e-3, abs(want) * 1e-3)
            what = f"{a}{b} 的长度"

        elif kind in ("angle", "deg", "degree"):
            vertex = _name(raw.get("vertex") or raw.get("v"))
            arms = raw.get("arms") or raw.get("of") or []
            if not (vertex and isinstance(arms, list) and len(arms) >= 2) or target is None:
                continue
            a, b = _name(arms[0]), _name(arms[1])
            if not (scene.has(a) and scene.has(vertex) and scene.has(b)):
                continue
            got = _angle(scene.coord(a), scene.coord(vertex), scene.coord(b))
            want = _f(target)
            ok = abs(got - want) <= 0.5
            what = f"∠{a}{vertex}{b}"

        elif kind == "slope":
            pair = raw.get("of") or raw.get("points") or []
            if not (isinstance(pair, list) and len(pair) >= 2) or target is None:
                continue
            a, b = _name(pair[0]), _name(pair[1])
            if not (scene.has(a) and scene.has(b)):
                continue
            (x1, y1), (x2, y2) = scene.coord(a), scene.coord(b)
            if abs(x2 - x1) < 1e-9:
                scene.warnings.append(f"自检无法计算 {a}{b} 的斜率（竖直）")
                continue
            got = (y2 - y1) / (x2 - x1)
            want = _f(target)
            ok = abs(got - want) <= max(0.01, abs(want) * 0.01)
            what = f"斜率 {a}{b}"

        elif kind in ("on_circle", "circle"):
            p = _name(raw.get("of") or raw.get("point"))
            center = _name(raw.get("center") or "O")
            if not (p and scene.has(p) and scene.has(center)):
                continue
            if target is not None:
                r = _f(target)
            elif raw.get("radius") is not None:
                r = _f(raw["radius"])
            elif raw.get("through") and scene.has(_name(raw["through"])):
                r = math.dist(scene.coord(center), scene.coord(_name(raw["through"])))
            else:
                continue
            got = math.dist(scene.coord(p), scene.coord(center))
            want = r
            ok = abs(got - r) <= max(1e-3, abs(r) * 0.01)
            what = f"{p} 到 {center} 的距离（半径）"

        elif kind in ("perpendicular", "parallel"):
            p1 = raw.get("of") or []
            p2 = raw.get("to") or []
            if not (isinstance(p1, list) and len(p1) >= 2 and isinstance(p2, list) and len(p2) >= 2):
                continue
            n1 = [_name(x) for x in p1[:2]]
            n2 = [_name(x) for x in p2[:2]]
            if not all(scene.has(x) for x in n1 + n2):
                continue
            d1 = _vec(scene.coord(n1[1]), scene.coord(n1[0]))
            d2 = _vec(scene.coord(n2[1]), scene.coord(n2[0]))
            ang = _angle_between(d1, d2)
            got = 90.0 - ang if kind == "perpendicular" else ang
            ok = abs(got) <= 0.5
            what = f"{n1[0]}{n1[1]} ⊥ {n2[0]}{n2[1]}" if kind == "perpendicular" else f"{n1[0]}{n1[1]} ∥ {n2[0]}{n2[1]}"

        elif kind == "collinear":
            names = [_name(x) for x in (raw.get("of") or [])]
            if len(names) < 3 or not all(scene.has(x) for x in names):
                continue
            (x1, y1), (x2, y2), (x3, y3) = (scene.coord(n) for n in names[:3])
            got = abs((x2 - x1) * (y3 - y1) - (y2 - y1) * (x3 - x1)) / (math.dist((x1, y1), (x2, y2)) or 1.0)
            ok = got <= 0.02
            what = "共线 " + "".join(names[:3])

        else:
            continue

        if ok is None:
            continue
        results.append({"what": what, "want": want, "got": round(got, 4), "ok": ok})
        if not ok:
            scene.warnings.append(f"自检不一致：{what} 按题设为 {want:g}，画出来是 {got:.3f}")

    scene.meta["checks"] = results


def _vec(a, b):
    return (b[0] - a[0], b[1] - a[1])


def _angle_between(d1, d2) -> float:
    n1 = math.hypot(*d1) or 1.0
    n2 = math.hypot(*d2) or 1.0
    c = max(-1.0, min(1.0, (d1[0] * d2[0] + d1[1] * d2[1]) / (n1 * n2)))
    return math.degrees(math.acos(c))
