"""把 Scene 渲染成 GeoGebra 能用的页面和命令。

GeoGebra 6 网页版的输入栏不接受 SetColor、SetLineThickness 这类命令，
所以文本里只保留“创建对象”的语句，颜色和线型交给 HTML 里的 JS API。
"""

from __future__ import annotations

import json
import os
import re
import shutil

from .model import Scene, fmt, infer_faces, section_polygon
from .textnorm import to_plain

_TPL = os.path.join(os.path.dirname(__file__), "templates", "figure.html")


def _rgb(hex_color: str) -> list[int]:
    h = hex_color.lstrip("#")
    return [int(h[i : i + 2], 16) for i in (0, 2, 4)]


def _quote(text: str) -> str:
    return json.dumps(text, ensure_ascii=False)


def _pt(x: float, y: float, z: float = 0.0, dimension: str = "2D") -> str:
    if dimension == "3D":
        return f"({fmt(x)},{fmt(y)},{fmt(z)})"
    return f"({fmt(x)},{fmt(y)})"


def build(scene: Scene, dynamic: bool = True, style: dict | None = None) -> tuple[list[str], list[dict]]:
    """返回 (命令列表, 样式列表)。"""
    style = style or {}
    main = style.get("main_color") or "#1F5C46"
    aux = style.get("aux_color") or "#8FD3A8"
    aux_dashed = bool(style.get("aux_dashed", True))
    dimension = str(style.get("dimension") or "2D").upper()
    color_style = str(style.get("style_3d") or "彩色实体") == "彩色实体"
    palette = ["#E8A0BF", "#8FD3A8", "#A0C4E8", "#E8C98F", "#C9A0E8", "#F2A68A"]
    face_idx = 0
    cmds: list[str] = []
    styles: list[dict] = []

    for p in scene.params:
        cmds.append(f"{p.name}={fmt(p.value)}")
        # 网页版里数字默认不可见，需要显式显示成滑动条
        styles.append({"name": p.name, "visible": True})

    for p in scene.points:
        if dynamic and p.dynamic and dimension != "3D":
            cmds.append(f"{p.label}={p.dynamic}")
        else:
            cmds.append(f"{p.label}={_pt(p.x, p.y, p.z, dimension)}")
        st: dict = {"name": p.label, "pointSize": 5, "labelVisible": True}
        if p.role == "auxiliary":
            st["visible"] = False
        st["color"] = _rgb(p.color or main)
        styles.append(st)

    for i, s in enumerate(scene.segments, 1):
        if not (scene.has(s.a) and scene.has(s.b)):
            continue
        name = f"s{i}"
        cmds.append(f"{name}=Segment({s.a},{s.b})")
        styles.append(
            {
                "name": name,
                "color": _rgb(s.color or main),
                "thickness": int(round(s.thickness)),
                "style": 1 if s.dashed else 0,
            }
        )

    for i, poly in enumerate(scene.polygons, 1):
        if len(poly.points) < 3 or not all(scene.has(n) for n in poly.points):
            continue
        if not poly.fill:
            continue  # 不填充时，边已经由 segments 画出来了
        name = f"poly{i}"
        cmds.append(f"{name}=Polygon({','.join(poly.points)})")
        face_color = palette[face_idx % len(palette)] if (dimension == "3D" and color_style) else (poly.color or "#1a1a1a")
        face_idx += 1
        styles.append(
            {
                "name": name,
                "color": _rgb(face_color),
                "thickness": 2,
                "style": 0,
                "fill": bool(poly.fill),
                "filling": 0.22 if dimension == "3D" else 0.18,
            }
        )

    if dimension == "3D":
        seen_faces = set()
        for poly in scene.polygons:
            seen_faces.add(frozenset(poly.points))
        for idx, face in enumerate(infer_faces(scene), 1):
            key = frozenset(face)
            if key in seen_faces or len(face) < 3:
                continue
            seen_faces.add(key)
            name = f"af{idx}"
            cmds.append(f"{name}=Polygon({','.join(face)})")
            face_color = palette[face_idx % len(palette)] if color_style else main
            face_idx += 1
            styles.append({"name": name, "color": _rgb(face_color), "fill": True, "filling": 0.22, "thickness": 1})

    for i, ln in enumerate(scene.lines, 1):
        if not (scene.has(ln.a) and scene.has(ln.b)):
            continue
        name = f"ln{i}"
        cmds.append(f"{name}=Line({ln.a},{ln.b})")
        styles.append(
            {
                "name": name,
                "color": _rgb(ln.color or aux),
                "thickness": 2,
                "style": 1 if (ln.dashed and aux_dashed) else 0,
            }
        )

    for i, c in enumerate(scene.circles, 1):
        if not scene.has(c.center):
            continue
        name = f"c{i}"
        if c.through and scene.has(c.through):
            cmds.append(f"{name}=Circle({c.center},{c.through})")
        else:
            cmds.append(f"{name}=Circle({c.center},{fmt(c.radius or 3.0)})")
        styles.append({"name": name, "color": _rgb(c.color or main), "thickness": 3, "style": 0})

    for f in scene.funcs:
        if dimension == "3D":
            continue
        cmds.append(f"{f.name}(x)={f.expr}")
        styles.append(
            {
                "name": f.name,
                "color": _rgb(f.color or "#c0392b"),
                "thickness": int(round(f.thickness)),
                "style": 1 if f.dashed else 0,
            }
        )

    for i, a in enumerate(scene.angles, 1):
        if not (scene.has(a.a) and scene.has(a.vertex) and scene.has(a.b)):
            continue
        name = f"ang{i}"
        cmds.append(f"{name}=Angle({a.a},{a.vertex},{a.b})")
        styles.append({"name": name, "color": _rgb(a.color or "#34495e"), "thickness": 2, "style": 0})

    xmin, xmax, ymin, ymax = scene.view()
    span_x, span_y = xmax - xmin, ymax - ymin
    tid = 0

    # 参考线：横线/竖线 + 文字标签
    for i, ln in enumerate(scene.ref_lines, 1):
        if dimension == "3D":
            continue
        name = f"L{i}"
        if ln.kind == "h":
            cmds.append(f"{name}=Line(({fmt(xmin)},{fmt(ln.value)}),({fmt(xmax)},{fmt(ln.value)}))")
            lx, ly = xmin + 0.80 * span_x, ln.value + 0.025 * span_y
        else:
            cmds.append(f"{name}=Line(({fmt(ln.value)},{fmt(ymin)}),({fmt(ln.value)},{fmt(ymax)}))")
            lx, ly = ln.value + 0.015 * span_x, ymin + 0.06 * span_y
        styles.append({"name": name, "color": _rgb(ln.color), "thickness": 2, "style": 1})
        if ln.label:
            tid += 1
            tname = f"t{tid}"
            cmds.append(f"{tname}=Text({_quote(ln.label)},({fmt(lx)},{fmt(ly)}))")
            styles.append({"name": tname, "color": _rgb(ln.color)})

    # 长度数字等零散标注（超出视野就挪进来）
    for t in scene.texts:
        if dimension == "3D":
            continue
        tid += 1
        tx = min(max(t.x, xmin + 0.04 * span_x), xmax - 0.04 * span_x)
        ty = min(max(t.y, ymin + 0.04 * span_y), ymax - 0.04 * span_y)
        cmds.append(f"t{tid}=Text({_quote(to_plain(t.text))},({fmt(tx)},{fmt(ty)}))")
        styles.append({"name": f"t{tid}", "color": _rgb(t.color or "#495057")})

    # 题目文字块：一行一个 Text，锚点用坐标字面量（不会生成多余的点）
    if scene.text_blocks and dimension != "3D":
        gap = 0.075 * span_y
        y0 = ymax - 0.19 * span_y  # 给左上角的参数滑动条让出位置
        x0 = xmin + 0.03 * span_x
        for blk in scene.text_blocks:
            for i, line in enumerate(blk.lines):
                tid += 1
                cmds.append(f"t{tid}=Text({_quote(line)},({fmt(x0)},{fmt(y0 - i * gap)}))")
                styles.append({"name": f"t{tid}", "color": _rgb(blk.color or "#20242a")})

    return cmds, styles


def commands(scene: Scene, dynamic: bool = True) -> list[str]:
    return build(scene, dynamic)[0]


def static_commands(scene: Scene) -> list[str]:
    return commands(scene, dynamic=False)


def paste_line(cmds: list[str]) -> str:
    body = ",".join(json.dumps(c, ensure_ascii=False) for c in cmds)
    return f"Execute[{{{body}}}]"


def _json_for_script(obj) -> str:
    return json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def html_page(scene: Scene, title: str = "math2geo", style: dict | None = None) -> str:
    style = style or {}
    color_style = str(style.get("style_3d") or "彩色实体") == "彩色实体"
    cmds, styles = build(scene, dynamic=True, style=style)
    steps = [
        {"title": to_plain(s.title), "body": to_plain(s.body), "action": s.action}
        for s in scene.steps
    ]
    if str(style.get("dimension") or "2D").upper() == "3D" and bool(style.get("section_show", True)):
        import math as _math

        az = _math.radians(float(style.get("section_azimuth", 35)))
        el = _math.radians(float(style.get("section_elevation", 20)))
        nx = _math.cos(el) * _math.cos(az)
        ny = _math.cos(el) * _math.sin(az)
        nz = _math.sin(el)
        ref = (0.0, 0.0, 1.0) if abs(nz) < 0.95 else (1.0, 0.0, 0.0)
        ux = ny * ref[2] - nz * ref[1]
        uy = nz * ref[0] - nx * ref[2]
        uz = nx * ref[1] - ny * ref[0]
        un = _math.sqrt(ux * ux + uy * uy + uz * uz) or 1.0
        ux, uy, uz = ux / un, uy / un, uz / un
        vx = ny * uz - nz * uy
        vy = nz * ux - nx * uz
        vz = nx * uy - ny * ux
        _xs = [p.x for p in scene.points]
        _ys = [p.y for p in scene.points]
        _zs = [p.z for p in scene.points]
        _cx = sum(_xs) / len(_xs) if _xs else 0.0
        _cy = sum(_ys) / len(_ys) if _ys else 0.0
        _cz = sum(_zs) / len(_zs) if _zs else 0.0
        _off = float(style.get("section_offset", 0.0) or 0.0)
        _cx, _cy, _cz = _cx + nx * _off, _cy + ny * _off, _cz + nz * _off
        _span = max(
            max(_xs) - min(_xs), max(_ys) - min(_ys), max(_zs) - min(_zs), 1.0
        ) * 0.55
        _corners = []
        for _su, _sv in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            _corners.append(
                (
                    _cx + (ux * _su + vx * _sv) * _span,
                    _cy + (uy * _su + vy * _sv) * _span,
                    _cz + (uz * _su + vz * _sv) * _span,
                )
            )
        _names = []
        _sec_styles = []
        for _i, (x, y, z) in enumerate(_corners, 1):
            _name = f"Sec{_i}"
            _names.append(_name)
            cmds.append(f"{_name}=({fmt(x)},{fmt(y)},{fmt(z)})")
            _sec_styles.append({"name": _name, "visible": False, "pointSize": 1})
        cmds.append(f"secPlane=Polygon({','.join(_names)})")
        styles.extend(_sec_styles)
        styles.append({
            "name": "secPlane",
            "color": _rgb("#E8A0BF" if color_style else "#8FD3A8"),
            "fill": True,
            "filling": max(0.0, min(0.8, float(style.get("section_opacity", 12) or 0) / 100.0)),
            "visible": True,
        })
        if bool(style.get("section_shape", True)):
            _sp = section_polygon(scene, (nx, ny, nz), _off)
            if len(_sp) >= 3:
                _pnames = []
                for _i, (_x, _y, _z) in enumerate(_sp, 1):
                    _nm = f"SecS{_i}"
                    _pnames.append(_nm)
                    cmds.append(f"{_nm}=({fmt(_x)},{fmt(_y)},{fmt(_z)})")
                    styles.append({"name": _nm, "visible": False, "pointSize": 1})
                cmds.append(f"secShape=Polygon({','.join(_pnames)})")
                styles.append({
                    "name": "secShape",
                    "color": _rgb("#C06A5A"),
                    "fill": True,
                    "filling": 0.38,
                })
        if bool(style.get("section_axes", True)):
            _axlen = _span * 0.72
            for _nm, _coords, _col in (
                ("SecO", (_cx, _cy, _cz), "#5D6B63"),
                ("SecU", (_cx + ux * _axlen, _cy + uy * _axlen, _cz + uz * _axlen), "#C06A5A"),
                ("SecV", (_cx + vx * _axlen, _cy + vy * _axlen, _cz + vz * _axlen), "#5A8FC0"),
            ):
                cmds.append(f"{_nm}=({fmt(_coords[0])},{fmt(_coords[1])},{fmt(_coords[2])})")
                styles.append({"name": _nm, "visible": False, "pointSize": 1})
            cmds.extend([
                "SecAxisU=Segment(SecO,SecU)",
                "SecAxisV=Segment(SecO,SecV)",
            ])
            styles.extend([
                {"name": "SecAxisU", "color": _rgb("#C06A5A"), "thickness": 2, "style": 0},
                {"name": "SecAxisV", "color": _rgb("#5A8FC0"), "thickness": 2, "style": 0},
            ])

    param_init = {p.name: p.value for p in scene.params}

    hint = ""
    if scene.params or scene.funcs:
        names = "、".join(p.name for p in scene.params) or "参数"
        hint = (
            f'<p class="hint">拖动参数 {names} 的滑动条可以看曲线变化；'
            "右侧是解答步骤，点每步的「在图中查看」会高亮对应图形。</p>"
        )

    if style.get("show_difficulty") and scene.meta.get("difficulty") is not None:
        hint += f'<p class="hint">难度系数 {float(scene.meta["difficulty"]):.2f}（越小越难）</p>'
    if style.get("show_breakthrough") and scene.meta.get("breakthrough"):
        hint += f'<p class="hint">突破点：{_esc(str(scene.meta["breakthrough"]))}</p>'

    warn_html = ""
    if scene.warnings:
        items = "".join(f"<li>{_esc(w)}</li>" for w in scene.warnings)
        warn_html = f'<div class="warn"><b>识别提示</b><ul>{items}</ul></div>'

    with open(_TPL, "r", encoding="utf-8") as fh:
        tpl = fh.read()


    return (
        tpl.replace("__TITLE__", _esc(title))
        .replace("__PROBLEM__", _esc(to_plain(scene.problem_text).replace("\n", " ")))
        .replace("__HINT__", hint)
        .replace("__WARN__", warn_html)
        .replace("__NCMDS__", str(len(cmds)))
        .replace("__CMDS_TEXT__", _esc("\n".join(cmds)))
        .replace("__CMDS_JSON__", _json_for_script(cmds))
        .replace("__STYLES_JSON__", _json_for_script(styles))
        .replace("__STEPS_JSON__", _json_for_script(steps))
        .replace("__BOUNDS_JSON__", _json_for_script(list(scene.view())))
        .replace("__AXES__", "true" if style.get("axes") else "false")
        .replace("__DIMENSION__", "3D" if str(style.get("dimension") or "2D").upper() == "3D" else "2D")
        .replace("__INIT_JSON__", _json_for_script(param_init))
    )



def _section_page_data(scene: Scene, style: dict):
    import math as _math

    az = _math.radians(float(style.get("section_azimuth", 35)))
    el = _math.radians(float(style.get("section_elevation", 20)))
    nx, ny, nz = _math.cos(el) * _math.cos(az), _math.cos(el) * _math.sin(az), _math.sin(el)
    ref = (0.0, 0.0, 1.0) if abs(nz) < 0.95 else (1.0, 0.0, 0.0)
    ux = ny * ref[2] - nz * ref[1]
    uy = nz * ref[0] - nx * ref[2]
    uz = nx * ref[1] - ny * ref[0]
    un = _math.sqrt(ux * ux + uy * uy + uz * uz) or 1.0
    ux, uy, uz = ux / un, uy / un, uz / un
    vx = ny * uz - nz * uy
    vy = nz * ux - nx * uz
    vz = nx * uy - ny * ux
    pts = [(p.x, p.y, p.z) for p in scene.points]
    cx = sum(p[0] for p in pts) / len(pts) if pts else 0.0
    cy = sum(p[1] for p in pts) / len(pts) if pts else 0.0
    cz = sum(p[2] for p in pts) / len(pts) if pts else 0.0
    span = max(
        max((p[0] for p in pts), default=0) - min((p[0] for p in pts), default=0),
        max((p[1] for p in pts), default=0) - min((p[1] for p in pts), default=0),
        max((p[2] for p in pts), default=0) - min((p[2] for p in pts), default=0),
        1.0,
    ) * 0.55
    off = float(style.get("section_offset", 0.0) or 0.0)
    cx, cy, cz = cx + nx * off, cy + ny * off, cz + nz * off
    corners = []
    for su, sv in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        corners.append((cx + (ux * su + vx * sv) * span,
                        cy + (uy * su + vy * sv) * span,
                        cz + (uz * su + vz * sv) * span))

    cmds, styles = [], []
    names = []
    for i, (x, y, z) in enumerate(corners, 1):
        name = f"Sec{i}"
        names.append(name)
        cmds.append(f"{name}=({fmt(x)},{fmt(y)},{fmt(z)})")
        styles.append({"name": name, "visible": False, "pointSize": 1})
    cmds.append(f"secPlane=Polygon({','.join(names)})")
    styles.append({
        "name": "secPlane",
        "color": _rgb("#E8A0BF" if str(style.get("style_3d", "彩色实体")) == "彩色实体" else "#8FD3A8"),
        "fill": True,
        "filling": max(0.0, min(0.8, float(style.get("section_opacity", 12) or 0) / 100.0)),
    })

    poly3 = section_polygon(scene, (nx, ny, nz), off)
    if len(poly3) >= 3:
        pnames = []
        for i, (x, y, z) in enumerate(poly3, 1):
            name = f"SecS{i}"
            pnames.append(name)
            cmds.append(f"{name}=({fmt(x)},{fmt(y)},{fmt(z)})")
            styles.append({"name": name, "visible": False, "pointSize": 1})
        cmds.append(f"secShape=Polygon({','.join(pnames)})")
        styles.append({"name": "secShape", "color": _rgb("#C06A5A"), "fill": True, "filling": 0.38})

    if bool(style.get("section_axes", True)):
        axlen = span * 0.72
        for name, coords, color in (
            ("SecAxisO", (cx, cy, cz), "#5D6B63"),
            ("SecAxisU", (cx + ux * axlen, cy + uy * axlen, cz + uz * axlen), "#C06A5A"),
            ("SecAxisV", (cx + vx * axlen, cy + vy * axlen, cz + vz * axlen), "#5A8FC0"),
        ):
            cmds.append(f"{name}=({fmt(coords[0])},{fmt(coords[1])},{fmt(coords[2])})")
            styles.append({"name": name, "visible": False, "pointSize": 1})
        cmds.append("SecAxisULine=Segment(SecAxisO,SecAxisU)")
        cmds.append("SecAxisVLine=Segment(SecAxisO,SecAxisV)")
        styles.append({"name": "SecAxisULine", "color": _rgb("#C06A5A"), "thickness": 2})
        styles.append({"name": "SecAxisVLine", "color": _rgb("#5A8FC0"), "thickness": 2})

    section2d = []
    for x, y, z in poly3:
        dx, dy, dz = x - cx, y - cy, z - cz
        section2d.append([round(dx * ux + dy * uy + dz * uz, 4),
                          round(dx * vx + dy * vy + dz * vz, 4)])
    return cmds, styles, section2d


def html_page_3d(scene: Scene, title: str = "math2geo", style: dict | None = None) -> str:
    style = style or {}
    if scene.points:
        # 把图形平移到原点附近，保证 GeoGebra 3D 默认视图里尽量居中
        work = Scene.from_dict(json.loads(scene.to_json()))
        cx = sum(p.x for p in work.points) / len(work.points)
        cy = sum(p.y for p in work.points) / len(work.points)
        cz = sum(p.z for p in work.points) / len(work.points)
        for p in work.points:
            p.x -= cx
            p.y -= cy
            p.z -= cz
        scene = work
    cmds, styles = build(scene, dynamic=True, style=style)
    sec_cmds, sec_styles, section2d = _section_page_data(scene, style)
    # 3D HTML 不再创建截面平面/截面坐标系，只保留截面图形
    _skip = ("Sec1=", "Sec2=", "Sec3=", "Sec4=", "secPlane=", "SecAxis", "secShape=")
    sec_cmds = [c for c in sec_cmds if not c.startswith(_skip)]
    _skip_names = {"Sec1", "Sec2", "Sec3", "Sec4", "secPlane",
                   "SecAxisO", "SecAxisU", "SecAxisV", "SecAxisULine", "SecAxisVLine"}
    sec_styles = [x for x in sec_styles if x.get("name") not in _skip_names]
    cmds.extend(sec_cmds)
    styles.extend(sec_styles)
    steps = [
        {"title": to_plain(s.title), "body": to_plain(s.body)} for s in scene.steps
    ]
    hint = '<p class="hint">拖动三维视图可自由旋转；右侧为当前截面在平面直角坐标系中的形状。</p>'
    if style.get("show_difficulty") and scene.meta.get("difficulty") is not None:
        hint += f'<p class="hint">难度系数 {float(scene.meta["difficulty"]):.2f}（越小越难）</p>'
    if style.get("show_breakthrough") and scene.meta.get("breakthrough"):
        hint += f'<p class="hint">突破点：{_esc(str(scene.meta["breakthrough"]))}</p>'
    warn_html = ""
    if scene.warnings:
        items = "".join(f"<li>{_esc(w)}</li>" for w in scene.warnings)
        warn_html = f'<div class="warn"><b>识别提示</b><ul>{items}</ul></div>'
    with open(os.path.join(os.path.dirname(__file__), "templates", "figure3d.html"), "r", encoding="utf-8") as fh:
        tpl = fh.read()
    return (
        tpl.replace("__TITLE__", _esc(title))
        .replace("__PROBLEM__", _esc(to_plain(scene.problem_text).replace("\n", " ")))
        .replace("__HINT__", hint)
        .replace("__WARN__", warn_html)
        .replace("__NCMDS__", str(len(cmds)))
        .replace("__CMDS_TEXT__", _esc("\n".join(cmds)))
        .replace("__CMDS_JSON__", _json_for_script(cmds))
        .replace("__STYLES_JSON__", _json_for_script(styles))
        .replace("__STEPS_JSON__", _json_for_script(steps))
        .replace("__POINTS3D_JSON__", _json_for_script({p.label: [p.x, p.y, p.z] for p in scene.points}))
        .replace("__FACES_JSON__", _json_for_script([
            list(poly.points) for poly in scene.polygons if poly.fill
        ] + [list(f) for f in infer_faces(scene)]))
        .replace("__SECTION_AZ__", str(float(style.get("section_azimuth", 35))))
        .replace("__SECTION_EL__", str(float(style.get("section_elevation", 20))))
        .replace("__SECTION_OFF__", str(float(style.get("section_offset", 0.0))))
        .replace("__AXES__", "true" if style.get("axes") else "false")
    )




def write(scene: Scene, outdir: str, stem: str = "figure", style: dict | None = None) -> dict[str, str]:
    style = style or {}
    os.makedirs(outdir, exist_ok=True)
    dyn, _ = build(scene, dynamic=True, style=style)
    sta = static_commands(scene)
    paths = {
        "dynamic": os.path.join(outdir, "geogebra_dynamic.txt"),
        "static": os.path.join(outdir, "geogebra_static.txt"),
        "paste": os.path.join(outdir, "geogebra_paste.txt"),
        "html": os.path.join(outdir, f"{stem}.html"),
    }
    _write_text(paths["dynamic"], "\n".join(dyn) + "\n")
    _write_text(paths["static"], "\n".join(sta) + "\n")
    _write_text(
        paths["paste"],
        "# 把下面这一行整行粘贴到 GeoGebra 输入栏并回车（Execute 在部分版本/网页版可用）\n"
        "# 若提示未知命令，请改用 geogebra_dynamic.txt 逐行粘贴\n"
        + paste_line(dyn)
        + "\n",
    )
    if str(style.get("dimension") or "2D").upper() == "3D":
        _write_text(paths["html"], html_page_3d(scene, title=stem, style=style))
    else:
        _write_text(paths["html"], html_page(scene, title=stem, style=style))
    if style.get("offline_bundle"):
        src = os.path.join(os.path.dirname(__file__), "..", "tools", "deployggb.js")
        if os.path.exists(src):
            dst = os.path.join(outdir, "deployggb.js")
            shutil.copy2(src, dst)
            paths["offline"] = dst
    return paths


def _write_text(path: str, content: str) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(content)
