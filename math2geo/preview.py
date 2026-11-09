"""预览图：尽量画得像课本插图那样干净。

几何题不画坐标轴和网格，标签往远离图形中心的方向摆并做简单避让，
直角画小方块、角画圆弧，圆心和半径都标出来。
"""

from __future__ import annotations

import math
import os
import tempfile
import textwrap

from .model import Scene, infer_faces, section_polygon
from .textnorm import to_plain

os.environ.setdefault("MPLCONFIGDIR", os.path.join(tempfile.gettempdir(), "math2geo-mpl"))

_FONTS = [
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
    r"C:\Windows\Fonts\simsun.ttc",
]

_INK = "#16181d"
_AUX = "#9aa3ad"
_CIRCLE = "#2b6cb0"
_DERIVED = "#e8590c"
_FILL = "#eef4fb"


def _font(size: float = 12):
    import matplotlib.font_manager as fm

    for path in _FONTS:
        try:
            return fm.FontProperties(fname=path, size=size)
        except Exception:
            continue
    return fm.FontProperties(size=size)


def render(scene: Scene, path: str, dpi: int = 170, show_title: bool = True, style: dict | None = None) -> str:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle, Polygon

    style = style or {}
    if str(style.get("dimension") or "2D").upper() == "3D":
        return _render_3d(scene, path, dpi=dpi, show_title=show_title, style=style)
    main = style.get("main_color") or _INK
    aux = style.get("aux_color") or _AUX
    axes_opt = style.get("axes")
    axes = bool(scene.funcs or scene.ref_lines or scene.meta.get("axes")) if axes_opt is None else bool(axes_opt)
    grid = axes and bool(style.get("grid", True))
    xmin, xmax, ymin, ymax = _view(scene)
    span = max(xmax - xmin, ymax - ymin, 1e-6)

    ratio = (ymax - ymin) / max(xmax - xmin, 1e-6)
    width = 8.0
    height = max(4.0, min(10.0, width * ratio))

    fig, ax = plt.subplots(figsize=(width, height))
    if style.get("show_difficulty") and scene.meta.get("difficulty") is not None:
        fig.text(0.02, 0.975, f"难度系数 {float(scene.meta['difficulty']):.2f}（越小越难）",
                 fontproperties=_font(9), color="#5D6B63", va="top")
    if style.get("show_breakthrough") and scene.meta.get("breakthrough"):
        fig.text(0.02, 0.948, f"突破点：{str(scene.meta['breakthrough'])[:60]}",
                 fontproperties=_font(9), color="#5D6B63", va="top")
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)

    if axes:
        ax.axhline(0, color="#d8dee6", lw=1, zorder=0)
        ax.axvline(0, color="#d8dee6", lw=1, zorder=0)
        if grid:
            ax.grid(True, color="#f1f4f8", lw=0.8, zorder=0)
        ax.tick_params(colors="#9aa3ad", labelsize=8)
        for spine in ax.spines.values():
            spine.set_visible(False)
    else:
        ax.axis("off")

    # ---- 填充多边形
    for poly in scene.polygons:
        if len(poly.points) < 3 or not all(scene.has(n) for n in poly.points):
            continue
        pts = [scene.coord(n) for n in poly.points]
        if poly.fill:
            ax.add_patch(Polygon(pts, closed=True, facecolor=_FILL, edgecolor="none", zorder=1))

    # ---- 线段
    for seg in scene.segments:
        if not (scene.has(seg.a) and scene.has(seg.b)):
            continue
        (x1, y1), (x2, y2) = scene.coord(seg.a), scene.coord(seg.b)
        ax.plot(
            [x1, x2],
            [y1, y2],
            color=seg.color or main,
            lw=seg.thickness,
            ls=(0, (5, 3)) if seg.dashed else "-",
            solid_capstyle="round",
            zorder=3,
        )

    # ---- 直线（无限长，按视图裁剪）
    for ln in scene.lines:
        if not (scene.has(ln.a) and scene.has(ln.b)):
            continue
        ax.axline(
            scene.coord(ln.a),
            scene.coord(ln.b),
            color=ln.color or aux,
            lw=1.4,
            ls=(0, (6, 4)) if ln.dashed else "-",
            zorder=2,
        )

    # ---- 圆
    for c in scene.circles:
        if not scene.has(c.center):
            continue
        cx, cy = scene.coord(c.center)
        r = c.radius
        if r is None and c.through and scene.has(c.through):
            r = math.dist((cx, cy), scene.coord(c.through))
        if not r:
            continue
        ax.add_patch(Circle((cx, cy), r, fill=False, ec=c.color or main, lw=1.8, zorder=2))

    # ---- 函数
    from . import algebra

    if scene.funcs:
        values = {p.name: p.value for p in scene.params}
        for f in scene.funcs:
            expr = algebra.to_sympy(f.expr)
            if expr is None:
                continue
            xs = [f.xmin + (f.xmax - f.xmin) * i / 600 for i in range(601)]
            ys = algebra.numeric_points(expr, xs, values)
            ax.plot(
                xs,
                ys,
                color=f.color or "#c0392b",
                lw=f.thickness * 0.75,
                ls=(0, (6, 3)) if f.dashed else "-",
                zorder=4,
            )

    # ---- 参考线
    for ln in scene.ref_lines:
        if ln.kind == "h":
            ax.axhline(ln.value, color=ln.color, lw=1.3, ls=(0, (4, 3)), zorder=2)
            ax.text(
                xmax - 0.02 * span,
                ln.value,
                " " + to_plain(ln.label or ""),
                color=ln.color,
                fontsize=9,
                va="bottom",
                ha="right",
                fontproperties=_font(9),
                zorder=9,
            )
        else:
            ax.axvline(ln.value, color=ln.color, lw=1.3, ls=(0, (4, 3)), zorder=2)
            ax.text(
                ln.value,
                ymin + 0.02 * span,
                " " + to_plain(ln.label or ""),
                color=ln.color,
                fontsize=9,
                va="bottom",
                ha="left",
                fontproperties=_font(9),
                zorder=9,
            )

    # ---- 角标记
    for a in scene.angles:
        _draw_angle(ax, scene, a, span)

    # ---- 点与标签
    _draw_points(ax, scene, span)

    # ---- 文字标注

    for t in scene.texts:
        ax.text(
            t.x,
            t.y,
            to_plain(t.text),
            fontsize=min(t.size * 0.72, 12),
            color=t.color or "#3d4652",
            ha="center",
            va="center",
            zorder=8,
            fontproperties=_font(min(t.size * 0.72, 12)),
        )

    # ---- 题干
    bottom = 0.04
    if show_title and style.get("include_problem", True) and scene.problem_text:
        title = textwrap.fill(to_plain(scene.problem_text).replace("\n", " "), 46)
        fig.text(
            0.5,
            0.012,
            title,
            ha="center",
            va="bottom",
            fontsize=9.5,
            color="#5b6470",
            fontproperties=_font(9.5),
            linespacing=1.5,
        )
        bottom = 0.03 + 0.026 * max(1, title.count("\n") + 1)

    if scene.params:
        txt = "   ".join(f"{p.name} = {p.value:g}" for p in scene.params)
        ax.text(
            0.99,
            0.02,
            txt,
            transform=ax.transAxes,
            ha="right",
            va="bottom",
            fontsize=9.5,
            color="#2c3e50",
            fontproperties=_font(9.5),
            bbox=dict(boxstyle="round,pad=0.35", facecolor="#eef4fb", edgecolor="#c9d8ea"),
        )

    fig.subplots_adjust(left=0.075 if axes else 0.02, right=0.98, top=0.985, bottom=bottom)
    fig.savefig(path, dpi=dpi, facecolor="white")
    plt.close(fig)
    return path


# ------------------------------------------------------------------ 取景



def _render_3d(scene: Scene, path: str, dpi: int = 170, show_title: bool = True, style: dict | None = None) -> str:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    style = style or {}
    main = style.get("main_color") or "#1F5C46"
    aux = style.get("aux_color") or "#8FD3A8"

    pts = {p.label: (p.x, p.y, p.z) for p in scene.points}
    if not pts:
        pts = {"O": (0.0, 0.0, 0.0)}
    xs = [v[0] for v in pts.values()]
    ys = [v[1] for v in pts.values()]
    zs = [v[2] for v in pts.values()]
    span = max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs), 1.0) * 1.35
    cx = (max(xs) + min(xs)) / 2
    cy = (max(ys) + min(ys)) / 2
    cz = (max(zs) + min(zs)) / 2

    fig = plt.figure(figsize=(7.2, 6.4))
    ax = fig.add_subplot(111, projection="3d")
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    palette = ["#E8A0BF", "#8FD3A8", "#A0C4E8", "#E8C98F", "#C9A0E8", "#F2A68A"]
    color_style = str(style.get("style_3d") or "彩色实体") == "彩色实体"
    face_alpha = 0.22 if color_style else 0.09
    face_keys: set[frozenset[str]] = set()
    face_count = 0
    for poly in scene.polygons:
        if not poly.fill or len(poly.points) < 3:
            continue
        verts = [pts[n] for n in poly.points if n in pts]
        if len(verts) >= 3:
            face_keys.add(frozenset(poly.points))
            face_color = palette[face_count % len(palette)] if color_style else (poly.color or main)
            face_count += 1
            ax.add_collection3d(
                Poly3DCollection([verts], alpha=face_alpha, facecolor=face_color, edgecolor="none")
            )
    for face in infer_faces(scene):
        key = frozenset(face)
        if key in face_keys:
            continue
        face_keys.add(key)
        verts = [pts[n] for n in face if n in pts]
        if len(verts) >= 3:
            face_color = palette[face_count % len(palette)] if color_style else main
            face_count += 1
            ax.add_collection3d(
                Poly3DCollection([verts], alpha=face_alpha, facecolor=face_color, edgecolor="none")
            )

    for seg in scene.segments:
        if seg.a in pts and seg.b in pts:
            a, b = pts[seg.a], pts[seg.b]
            ax.plot(
                [a[0], b[0]], [a[1], b[1]], [a[2], b[2]],
                color=seg.color or main,
                linewidth=seg.thickness * 0.7,
                linestyle="--" if seg.dashed else "-",
            )

    for p in scene.points:
        if p.role == "auxiliary":
            continue
        ax.scatter([p.x], [p.y], [p.z], s=max(14, p.size * 5), color=p.color or main, depthshade=False)
        if p.show_label:
            ax.text(p.x, p.y, p.z, f" {p.label}", color="#20242a", fontsize=9)

    if bool(style.get("section_show", True)):
        az = math.radians(float(style.get("section_azimuth", 35)))
        el = math.radians(float(style.get("section_elevation", 20)))
        nx, ny, nz = math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), math.sin(el)
        # 平面内两个正交基
        ref = (0.0, 0.0, 1.0) if abs(nz) < 0.95 else (1.0, 0.0, 0.0)
        ux = ny * ref[2] - nz * ref[1]
        uy = nz * ref[0] - nx * ref[2]
        uz = nx * ref[1] - ny * ref[0]
        un = math.sqrt(ux * ux + uy * uy + uz * uz) or 1.0
        ux, uy, uz = ux / un, uy / un, uz / un
        vx = ny * uz - nz * uy
        vy = nz * ux - nx * uz
        vz = nx * uy - ny * ux
        size = span * 0.55
        off = float(style.get("section_offset", 0.0) or 0.0)
        pcx, pcy, pcz = cx + nx * off, cy + ny * off, cz + nz * off
        corners = []
        for su, sv in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            corners.append((pcx + (ux * su + vx * sv) * size,
                            pcy + (uy * su + vy * sv) * size,
                            pcz + (uz * su + vz * sv) * size))
        alpha = max(0.0, min(0.8, float(style.get("section_opacity", 12) or 0) / 100.0))
        ax.add_collection3d(
            Poly3DCollection(
                [corners],
                alpha=alpha,
                facecolor="#E8A0BF" if color_style else "#8FD3A8",
                edgecolor="#5A8FC0",
            )
        )
        if bool(style.get("section_shape", True)):
            secpts = section_polygon(scene, (nx, ny, nz), off)
            if len(secpts) >= 3:
                ax.add_collection3d(
                    Poly3DCollection(
                        [secpts],
                        alpha=0.38,
                        facecolor="#E8A0BF" if color_style else "#8FD3A8",
                        edgecolor="#C06A5A",
                    )
                )
        if bool(style.get("section_axes", True)):
            for _dir, _label, _color in (
                ((ux, uy, uz), "u", "#C06A5A"),
                ((vx, vy, vz), "v", "#5A8FC0"),
            ):
                _ex = pcx + _dir[0] * size * 0.72
                _ey = pcy + _dir[1] * size * 0.72
                _ez = pcz + _dir[2] * size * 0.72
                ax.plot([pcx, _ex], [pcy, _ey], [pcz, _ez], color=_color, linewidth=1.2)
                ax.text(_ex, _ey, _ez, _label, color=_color, fontsize=8)

    ax.set_xlim(cx - span / 2, cx + span / 2)
    ax.set_ylim(cy - span / 2, cy + span / 2)
    ax.set_zlim(max(0.0, cz - span / 2), cz + span / 2 + 0.01)
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.set_zlabel("z")
    ax.view_init(elev=22, azim=-62)
    ax.grid(True, color="#E3EFE8", linewidth=0.7)
    for axis in (ax.xaxis, ax.yaxis, ax.zaxis):
        axis.pane.set_facecolor((1, 1, 1, 1))
        axis.pane.set_edgecolor("#D9E8DE")
    if show_title and scene.problem_text:
        fig.suptitle(scene.problem_text[:80], fontsize=9, color="#5D6B63")
    if style.get("show_difficulty") and scene.meta.get("difficulty") is not None:
        fig.text(0.02, 0.975, f"难度系数 {float(scene.meta['difficulty']):.2f}（越小越难）",
                 fontproperties=_font(9), color="#5D6B63", va="top")
    if style.get("show_breakthrough") and scene.meta.get("breakthrough"):
        fig.text(0.02, 0.948, f"突破点：{str(scene.meta['breakthrough'])[:60]}",
                 fontproperties=_font(9), color="#5D6B63", va="top")
    fig.tight_layout()
    fig.savefig(path, dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


def _view(scene: Scene):
    return scene.view()


# ------------------------------------------------------------------ 点与标签


def _draw_points(ax, scene: Scene, span: float) -> None:
    pts = [p for p in scene.points if p.role != "auxiliary"]
    if not pts:
        return
    cx = sum(p.x for p in pts) / len(pts)
    cy = sum(p.y for p in pts) / len(pts)

    placed: list[tuple[float, float]] = []
    min_gap = span * 0.055

    for p in pts:
        color = p.color or _INK
        ax.plot([p.x], [p.y], "o", ms=4.2, color=color, zorder=6)
        if not p.show_label:
            continue

        dx, dy = p.x - cx, p.y - cy
        if math.hypot(dx, dy) < span * 0.02:
            dx, dy = 0.7, 0.7
        base = math.atan2(dy, dx)
        best = None
        for delta in (0, 45, -45, 90, -90, 135, -135, 180):
            ang = base + math.radians(delta)
            lx = p.x + math.cos(ang) * span * 0.045
            ly = p.y + math.sin(ang) * span * 0.045
            if all(math.dist((lx, ly), (q.x, q.y)) > min_gap for q in pts if q is not p) and all(
                math.dist((lx, ly), pos) > min_gap for pos in placed
            ):
                best = (lx, ly)
                break
        if best is None:
            best = (p.x + math.cos(base) * span * 0.05, p.y + math.sin(base) * span * 0.05)
        placed.append(best)
        ax.text(
            best[0],
            best[1],
            p.label,
            fontsize=13,
            color=color,
            ha="center",
            va="center",
            zorder=8,
            fontproperties=_font(13),
        )


# ------------------------------------------------------------------ 角


def _draw_angle(ax, scene: Scene, a, span: float) -> None:
    from matplotlib.patches import Wedge

    if not (scene.has(a.a) and scene.has(a.vertex) and scene.has(a.b)):
        return
    vx, vy = scene.coord(a.vertex)
    p1, p2 = scene.coord(a.a), scene.coord(a.b)
    v1 = (p1[0] - vx, p1[1] - vy)
    v2 = (p2[0] - vx, p2[1] - vy)
    n1 = math.hypot(*v1) or 1.0
    n2 = math.hypot(*v2) or 1.0
    u1 = (v1[0] / n1, v1[1] / n1)
    u2 = (v2[0] / n2, v2[1] / n2)
    rad = max(0.25 * span * 0.12, min(min(n1, n2) * 0.22, span * 0.16))
    color = a.color or "#34495e"

    dot = max(-1.0, min(1.0, u1[0] * u2[0] + u1[1] * u2[1]))
    ang = math.degrees(math.acos(dot))

    if abs(ang - 90.0) < 1.5:
        s = rad * 0.55
        p1_ = (vx + u1[0] * s, vy + u1[1] * s)
        p2_ = (p1_[0] + u2[0] * s, p1_[1] + u2[1] * s)
        p3_ = (vx + u2[0] * s, vy + u2[1] * s)
        ax.plot([p1_[0], p2_[0], p3_[0]], [p1_[1], p2_[1], p3_[1]], color=color, lw=1.3, zorder=4)
        return

    th1 = math.atan2(u1[1], u1[0])
    th2 = math.atan2(u2[1], u2[0])
    d = (th2 - th1 + math.pi) % (2 * math.pi) - math.pi
    if abs(d) > math.pi:
        d = d - math.pi if d > 0 else d + math.pi
    ax.add_patch(
        Wedge((vx, vy), rad, math.degrees(th1), math.degrees(th1 + d), width=None,
              facecolor=color, alpha=0.07, edgecolor="none", zorder=2)
    )
    steps = 40
    xs = [vx + rad * math.cos(th1 + d * i / steps) for i in range(steps + 1)]
    ys = [vy + rad * math.sin(th1 + d * i / steps) for i in range(steps + 1)]
    ax.plot(xs, ys, color=color, lw=1.2, zorder=4)

    if a.label:
        mid = th1 + d / 2
        # 沿角平分线往外，再往侧面挪一点，免得压在角平分线上
        lx = vx + rad * 1.55 * math.cos(mid) - rad * 0.55 * math.sin(mid)
        ly = vy + rad * 1.55 * math.sin(mid) + rad * 0.55 * math.cos(mid)
        ax.text(
            lx,
            ly,
            to_plain(a.label),
            fontsize=9,
            color=color,
            ha="center",
            va="center",
            zorder=8,
            fontproperties=_font(9),
            bbox=dict(boxstyle="round,pad=0.15", facecolor="white", edgecolor="none", alpha=0.9),
        )
