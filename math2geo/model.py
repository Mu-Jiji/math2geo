"""Scene：整个项目共用的中间表示。

读题、算坐标、三种渲染器都只认这一份结构，彼此不直接耦合。
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class PointObj:
    label: str
    x: float
    y: float
    z: float = 0.0
    # 依赖构造表达式（GeoGebra 语法），如 "Midpoint(A,B)"。
    # 为 None 表示自由点，用坐标定义。
    dynamic: str | None = None
    show_label: bool = True
    color: str | None = None
    size: float = 4.0
    role: str = "vertex"  # vertex | derived | center | auxiliary | anchor
    note: str = ""



def infer_faces(scene: "Scene", max_len: int = 5) -> list[list[str]]:
    """从线段图里找无弦最小环，补出立体图形的各个面。"""
    labels = sorted({p.label for p in scene.points})
    index = {name: i for i, name in enumerate(labels)}
    adj: dict[str, set[str]] = {name: set() for name in labels}
    for seg in scene.segments:
        if seg.a in adj and seg.b in adj:
            adj[seg.a].add(seg.b)
            adj[seg.b].add(seg.a)

    faces: list[list[str]] = []
    seen: set[tuple[str, ...]] = set()

    def dfs(start: str, path: list[str]) -> None:
        if len(path) > max_len:
            return
        for nxt in sorted(adj[path[-1]], key=lambda n: index[n]):
            if nxt == start and len(path) >= 3:
                cycle = tuple(path)
                # 规范化（旋转后最小字典序）
                rev = tuple(reversed(cycle))
                variants = [cycle[i:] + cycle[:i] for i in range(len(cycle))]
                variants += [rev[i:] + rev[:i] for i in range(len(rev))]
                canon = min(variants)
                if canon in seen:
                    continue
                # 有弦的环不是面
                chord = False
                for i in range(len(path)):
                    for j in range(i + 2, len(path)):
                        if i == 0 and j == len(path) - 1:
                            continue
                        if path[j] in adj[path[i]]:
                            chord = True
                            break
                    if chord:
                        break
                if not chord:
                    seen.add(canon)
                    faces.append(list(canon))
                continue
            if nxt in path or index[nxt] < index[start]:
                continue
            dfs(start, path + [nxt])

    for name in labels:
        dfs(name, [name])
    return faces



def section_polygon(scene: "Scene", normal: tuple[float, float, float], offset: float = 0.0) -> list[tuple[float, float, float]]:
    """求截面与立体各面的交线，并按平面内角度排序成多边形。"""
    import math as _math

    nx, ny, nz = normal
    length = _math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
    nx, ny, nz = nx / length, ny / length, nz / length
    pts3 = {p.label: (p.x, p.y, p.z) for p in scene.points}
    if not pts3:
        return []
    cx = sum(v[0] for v in pts3.values()) / len(pts3)
    cy = sum(v[1] for v in pts3.values()) / len(pts3)
    cz = sum(v[2] for v in pts3.values()) / len(pts3)
    d = nx * (cx + nx * offset) + ny * (cy + ny * offset) + nz * (cz + nz * offset)

    faces: list[list[str]] = []
    for poly in scene.polygons:
        if poly.fill and len(poly.points) >= 3:
            faces.append(list(poly.points))
    for face in infer_faces(scene):
        if face not in faces:
            faces.append(face)

    hits: list[tuple[float, float, float]] = []
    for face in faces:
        verts = [pts3[n] for n in face if n in pts3]
        if len(verts) < 3:
            continue
        for i in range(len(verts)):
            a = verts[i]
            b = verts[(i + 1) % len(verts)]
            da = nx * a[0] + ny * a[1] + nz * a[2] - d
            db = nx * b[0] + ny * b[1] + nz * b[2] - d
            if abs(da) < 1e-7:
                hits.append(a)
            elif da * db < 0:
                t = da / (da - db)
                hits.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t))

    unique: list[tuple[float, float, float]] = []
    for p in hits:
        if not any(_math.dist(p, q) < 1e-5 for q in unique):
            unique.append(p)
    if len(unique) < 3:
        return []

    ref = (0.0, 0.0, 1.0) if abs(nz) < 0.95 else (1.0, 0.0, 0.0)
    ux = ny * ref[2] - nz * ref[1]
    uy = nz * ref[0] - nx * ref[2]
    uz = nx * ref[1] - ny * ref[0]
    un = _math.sqrt(ux * ux + uy * uy + uz * uz) or 1.0
    ux, uy, uz = ux / un, uy / un, uz / un
    vx = ny * uz - nz * uy
    vy = nz * ux - nx * uz
    vz = nx * uy - ny * ux
    ox, oy, oz = cx + nx * offset, cy + ny * offset, cz + nz * offset
    def angle(p):
        dx, dy, dz = p[0] - ox, p[1] - oy, p[2] - oz
        return _math.atan2(dx * vx + dy * vy + dz * vz, dx * ux + dy * uy + dz * uz)
    return sorted(unique, key=angle)


@dataclass
class SegmentObj:
    a: str
    b: str
    color: str | None = None
    dashed: bool = False
    thickness: float = 2.6
    role: str = "side"  # side | aux | diagonal | radius


@dataclass
class LineObj:
    a: str
    b: str
    color: str | None = None
    dashed: bool = True
    role: str = "aux"


@dataclass
class CircleObj:
    center: str
    through: str | None = None
    radius: float | None = None
    color: str | None = None
    dashed: bool = False
    label: str | None = None
    role: str = "circle"


@dataclass
class ParamObj:
    """含参问题里的参数，GeoGebra 里就是一条滑动条。"""

    name: str
    value: float = 1.0
    min: float = -5.0
    max: float = 5.0
    step: float = 0.1
    label: str | None = None


@dataclass
class FuncObj:
    name: str
    expr: str  # GeoGebra 可直接接受的表达式，例如 "x^2-4x+3"
    xmin: float
    xmax: float
    color: str | None = None
    params: list[str] = field(default_factory=list)
    dashed: bool = False
    thickness: float = 3.0
    role: str = "function"  # function | derivative | reference
    label: str | None = None
    display: str | None = None  # 给人看的写法，例如 (x^2+ax-a)/(e^x)


@dataclass
class RefLineObj:
    """水平/竖直参考线，例如 y=2/e²、x=2。"""

    kind: str  # "h" | "v"
    value: float
    label: str = ""
    color: str = "#8e44ad"


@dataclass
class TextBlockObj:
    """题目原文文字块，GeoGebra 里按行拆成多个 Text 对象。"""

    lines: list[str]
    size: float = 12.0
    color: str | None = "#20242a"
    anchor: str = "top-left"


@dataclass
class PolygonObj:
    points: list[str]
    color: str | None = None
    fill: bool = False


@dataclass
class AngleMark:
    a: str  # 角的一边上的点
    vertex: str
    b: str  # 另一边上的点
    label: str | None = None
    color: str | None = None


@dataclass
class TextObj:
    text: str
    x: float
    y: float
    size: float = 13.0
    color: str | None = None


@dataclass
class SolutionStep:
    """解答步骤：显示在 HTML 侧栏，可点击联动图形。"""

    title: str
    body: str = ""
    action: dict | None = None


def fmt(value: float | None) -> str:
    """坐标/长度显示：整数就写整数，其余保留 6 位有效数字。"""
    if value is None:
        return "?"
    if abs(value) < 1e-9:
        return "0"
    if abs(value - round(value)) < 1e-9:
        return str(int(round(value)))
    return f"{value:.6g}"


@dataclass
class Scene:
    problem_text: str = ""
    points: list[PointObj] = field(default_factory=list)
    segments: list[SegmentObj] = field(default_factory=list)
    lines: list[LineObj] = field(default_factory=list)
    circles: list[CircleObj] = field(default_factory=list)
    funcs: list[FuncObj] = field(default_factory=list)
    params: list[ParamObj] = field(default_factory=list)
    ref_lines: list[RefLineObj] = field(default_factory=list)
    text_blocks: list[TextBlockObj] = field(default_factory=list)
    polygons: list[PolygonObj] = field(default_factory=list)
    angles: list[AngleMark] = field(default_factory=list)
    steps: list[SolutionStep] = field(default_factory=list)
    texts: list[TextObj] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)

    # ---------- 查询 ----------

    def point(self, label: str) -> PointObj | None:
        for p in self.points:
            if p.label == label:
                return p
        return None

    def coord3(self, label: str) -> tuple[float, float, float]:
        p = self.point(label)
        if p is None:
            raise KeyError(label)
        return p.x, p.y, p.z

    def coord(self, label: str) -> tuple[float, float]:
        p = self.point(label)
        if p is None:
            raise KeyError(f"场景中没有点 {label}")
        return p.x, p.y

    def has(self, label: str) -> bool:
        return self.point(label) is not None

    # ---------- 视图范围 ----------

    def bounds(self, pad: float = 1.6) -> tuple[float, float, float, float]:
        if self.meta.get("view"):
            v = self.meta["view"]
            return (float(v[0]), float(v[1]), float(v[2]), float(v[3]))
        xs: list[float] = []
        ys: list[float] = []
        for p in self.points:
            if p.role in ("anchor", "auxiliary"):
                continue
            xs.append(p.x)
            ys.append(p.y)
        for c in self.circles:
            cx, cy = self.coord(c.center)
            r = c.radius if c.radius is not None else 3.0
            xs += [cx - r, cx + r]
            ys += [cy - r, cy + r]
        for f in self.funcs:
            ys.append(self._func_range(f)[0])
            ys.append(self._func_range(f)[1])
            xs += [f.xmin, f.xmax]
        if not xs:
            return (-5.0, 5.0, -5.0, 5.0)
        xmin, xmax = min(xs) - pad, max(xs) + pad
        ymin, ymax = min(ys) - pad, max(ys) + pad
        # 保持大致正方形视野，避免图形被拉伸
        w, h = xmax - xmin, ymax - ymin
        if w > 0 and h > 0:
            ratio = w / h
            if ratio > 1.35:
                need = w / 1.35
                ymin -= (need - h) / 2
                ymax += (need - h) / 2
            elif ratio < 0.74:
                need = h * 0.74
                xmin -= (need - w) / 2
                xmax += (need - w) / 2
        return (round(xmin, 3), round(xmax, 3), round(ymin, 3), round(ymax, 3))

    def view(self, pad_ratio: float = 0.10) -> tuple[float, float, float, float]:
        """紧贴图形的取景：辅助点不参与，四周留 pad_ratio，并压成近似正方形。"""
        view = self.meta.get("view")
        if isinstance(view, (list, tuple)) and len(view) == 4:
            try:
                return tuple(float(v) for v in view)  # type: ignore[return-value]
            except (TypeError, ValueError):
                pass

        xs: list[float] = []
        ys: list[float] = []
        for p in self.points:
            if p.role in ("auxiliary", "anchor"):
                continue
            xs.append(p.x)
            ys.append(p.y)
        for c in self.circles:
            if not self.has(c.center):
                continue
            cx, cy = self.coord(c.center)
            r = c.radius or 0.0
            if c.through and self.has(c.through):
                r = math.dist((cx, cy), self.coord(c.through))
            xs += [cx - r, cx + r]
            ys += [cy - r, cy + r]
        for f in self.funcs:
            xs += [f.xmin, f.xmax]
            lo, hi = self._func_range(f)
            ys += [lo, hi]
        if not xs:
            return (-5.0, 5.0, -5.0, 5.0)

        xmin, xmax = min(xs), max(xs)
        ymin, ymax = min(ys), max(ys)
        pad = max(xmax - xmin, ymax - ymin) * pad_ratio + 0.12
        xmin, xmax = xmin - pad, xmax + pad
        ymin, ymax = ymin - pad, ymax + pad
        w, h = xmax - xmin, ymax - ymin
        if w > h:
            extra = (w - h) / 2
            ymin, ymax = ymin - extra, ymax + extra
        else:
            extra = (h - w) / 2
            xmin, xmax = xmin - extra, xmax + extra
        return (xmin, xmax, ymin, ymax)

    def _func_range(self, f: FuncObj) -> tuple[float, float]:
        """粗略估计函数在 [xmin,xmax] 上的值域（只用于取景）。"""
        from . import algebra

        expr = algebra.to_sympy(f.expr)
        if expr is None:
            return (-5.0, 5.0)
        values = {p.name: p.value for p in self.params}
        xs = [f.xmin + (f.xmax - f.xmin) * i / 240 for i in range(241)]
        vals = []
        for v in algebra.numeric_points(expr, xs, values):
            if isinstance(v, (int, float)) and math.isfinite(v):
                vals.append(float(v))
        if not vals:
            return (-5.0, 5.0)
        # 用中位数 + 绝对偏差看“主体”，避免 x→渐近线处的巨大值把视野撑爆
        vals.sort()
        n = len(vals)
        med = vals[n // 2]
        mad = sorted(abs(v - med) for v in vals)[n // 2] or 1e-3
        lo = max(vals[int(n * 0.05)], med - 7 * mad)
        hi = min(vals[int(n * 0.95)], med + 7 * mad)
        # 再夹一层：中学函数的图基本不会需要 ±20 以外的纵向视野
        lo, hi = max(lo, -20.0), min(hi, 20.0)
        if hi <= lo:
            hi = lo + 1.0
        return (lo, hi)

    # ---------- 导出 ----------

    def to_json(self) -> str:
        data = asdict(self)
        data["bounds"] = self.bounds()
        return json.dumps(data, ensure_ascii=False, indent=2)

    @classmethod
    def from_dict(cls, data: dict) -> "Scene":
        """从 scene.json 还原（工具/测试用）。"""
        scene = cls(problem_text=str(data.get("problem_text") or ""))
        mapping = {
            "points": (PointObj, scene.points),
            "segments": (SegmentObj, scene.segments),
            "lines": (LineObj, scene.lines),
            "circles": (CircleObj, scene.circles),
            "funcs": (FuncObj, scene.funcs),
            "params": (ParamObj, scene.params),
            "ref_lines": (RefLineObj, scene.ref_lines),
            "text_blocks": (TextBlockObj, scene.text_blocks),
            "polygons": (PolygonObj, scene.polygons),
            "angles": (AngleMark, scene.angles),
            "steps": (SolutionStep, scene.steps),
            "texts": (TextObj, scene.texts),
        }
        for key, (klass, target) in mapping.items():
            for item in data.get(key) or []:
                if not isinstance(item, dict):
                    continue
                fields = {k: v for k, v in item.items() if k in klass.__dataclass_fields__}
                try:
                    target.append(klass(**fields))
                except TypeError:
                    continue
        scene.warnings = [str(w) for w in data.get("warnings") or []]
        scene.meta = dict(data.get("meta") or {})
        return scene
