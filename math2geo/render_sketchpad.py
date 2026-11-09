"""把 Scene 转成几何画板（Sketchpad）的分步构造说明。

几何画板的 .gsp 是私有二进制格式，没有公开的脚本接口，所以这里生成的
是“照着点就能画出来”的构造脚本：每步给出菜单路径、要选中的对象和坐标，
并且强调用「构造」命令而不是直接画点，这样图形才能拖动。
"""

from __future__ import annotations

import re

from .model import Scene, fmt

_ROLE_NAME = {
    "vertex": "顶点",
    "center": "圆心",
    "derived": "派生点",
    "auxiliary": "辅助点",
    "anchor": "锚点",
}

_CN = ["一", "二", "三", "四", "五", "六", "七", "八", "九", "十"]


def markdown(scene: Scene, title: str = "") -> str:
    name = title or "题目图形"
    sections: list[tuple[str, list[str]]] = []

    head: list[str] = [f"# 几何画板构造脚本：{name}", ""]
    if scene.text_blocks:
        for line in scene.text_blocks[0].lines:
            head.append(f"> {line}")
        head.append("")
    elif scene.problem_text:
        head += [f"> {scene.problem_text}", ""]

    sections.append(
        (
            "准备",
            [
                "1. 打开几何画板，新建文件（Ctrl+N）。",
                "2. 显示 → 显示坐标轴；如果要在整数格点上取点，可再选 显示 → 显示网格。",
                "3. 左侧选「箭头」工具，之后所有选择都用它。",
                "4. 记住一条原则：**能「构造」就不要手画**，否则拖动后图形会散。",
                "",
            ],
        )
    )

    base = [p for p in scene.points if p.role != "anchor" and not p.dynamic]
    derived = [p for p in scene.points if p.dynamic]

    if base:
        body = ["菜单：绘图 → 绘制点…，依次输入横、纵坐标后回车。", "", "| 点 | 坐标 | 说明 |", "| --- | --- | --- |"]
        for p in base:
            body.append(f"| {p.label} | ({fmt(p.x)}, {fmt(p.y)}) | {_ROLE_NAME.get(p.role, '点')} |")
        body.append("")
        sections.append(("绘制基础点", body))

    sides = [s for s in scene.segments if s.role in ("side", "radius")]
    aux = [s for s in scene.segments if s.role not in ("side", "radius")]

    if sides:
        body = ["选中两个点（点 A 后再按住 Shift 点 B），构造 → 线段。", ""]
        for s in sides:
            body.append(f"- 线段 {s.a}{s.b}" + ("（虚线，可 显示 → 线型 → 虚线）" if s.dashed else ""))
        body.append("")
        sections.append(("连线段", body))

    if scene.circles:
        body = []
        for c in scene.circles:
            r = c.radius if c.radius is not None else 3.0
            body.append(f"- 圆心 {c.center}，半径 {fmt(r)}。做法二选一：")
            body.append(
                f"  1. 选中圆心 {c.center} → 构造 → 以圆心和半径绘圆"
                f"（半径要先用「度量 → 长度」得到一条长度为 {fmt(r)} 的线段）；"
            )
            body.append(
                f"  2. 先在 ({fmt(r)}, 0) 处绘制一点作为圆周上的点，再选中圆心和该点 → 构造 → 以圆心和圆周上一点绘圆。"
            )
        body.append("")
        sections.append(("画圆", body))

    if scene.params:
        body = []
        for p in scene.params:
            body.append(f"- 数据 → 新建参数…，名称 `{p.name}`，值 {fmt(p.value)}。")
            body.append(
                f"  右键参数 {p.name} → 属性，把取值范围设成 [{fmt(p.min)}, {fmt(p.max)}]，"
                f"精度 {fmt(p.step)}；想让图动起来就 选中参数 → 编辑 → 操作类按钮 → 动画。"
            )
        body.append("")
        sections.append(("新建参数（滑动条）", body))

    if scene.funcs:
        body = []
        for f in scene.funcs:
            shown = f.display or f.expr
            if f.role == "derivative":
                body.append(f"- 导函数 `{f.label or f.name}`：")
                body.append("  1. 选中函数图像 → 构造 → 导函数（有的版本在「绘图」菜单里，名称是“导数”）；")
                body.append(f"  2. 或者直接再画一条：绘图 → 绘制新函数…，输入 `{shown}`，确定，再把线型改成虚线。")
            else:
                body.append(f"- 绘图 → 绘制新函数…，输入 `{shown}`，确定。")
                body.append("  如果 `e^x` 输不进去，可以试 `exp(x)`；画完 右键曲线 → 属性 调整颜色。")
            body.append(f"  提示：x 的范围建议取 [{fmt(f.xmin)}, {fmt(f.xmax)}]。")
        body.append("")
        sections.append(("画函数图像", body))

    if scene.ref_lines:
        body = []
        for ln in scene.ref_lines:
            if ln.kind == "h":
                body.append(
                    f"- 参考线 {ln.label or ('y=' + fmt(ln.value))}：在 (0, {fmt(ln.value)}) 和 (1, {fmt(ln.value)}) 各画一个点，"
                    f"选中两点 → 构造 → 直线，线型改虚线。"
                )
            else:
                body.append(
                    f"- 参考线 {ln.label or ('x=' + fmt(ln.value))}：在 ({fmt(ln.value)}, 0) 和 ({fmt(ln.value)}, 1) 各画一个点，"
                    f"选中两点 → 构造 → 直线，线型改虚线。"
                )
        body.append("")
        sections.append(("画参考线", body))

    if derived:
        body = []
        for i, p in enumerate(derived, 1):
            body.append(f"{i}. **{p.label}** —— {_describe(p.dynamic or '', p)}")
        body.append("")
        sections.append(("构造派生点", body))

    if aux:
        body = []
        for s in aux:
            note = "——对角线的交点用 构造 → 交点" if s.role == "diagonal" else ""
            body.append(f"- 线段 {s.a}{s.b}（虚线）{note}")
        body.append("")
        sections.append(("辅助线", body))

    if scene.angles or scene.texts:
        body = []
        if scene.angles:
            body.append("- 角标记：依次选三个点（边上一点 → 顶点 → 另一边一点），度量 → 角度；直角会自动画成小方块。")
        if scene.texts:
            lens = "、".join(t.text for t in scene.texts)
            body.append(f"- 边长数字：选中对应线段，度量 → 长度，把度量值拖到线段旁边（题目给的数值：{lens}）。")
        body.append("")
        sections.append(("标注与度量", body))

    if scene.params or scene.funcs:
        sections.append(
            (
                "检查",
                [
                    "1. 拖动参数 a 的动画按钮，观察曲线、导函数零点怎么变化。",
                    "2. 选中函数图像 → 度量 → 导数（或 构造 → 导函数），核对零点是否与题目一致。",
                    "3. 看参考线与曲线的位置关系，是否和题目里的不等关系相符。",
                    "",
                ],
            )
        )
    else:
        sections.append(
            (
                "检查",
                [
                    "1. 拖动任意一个自由点，看图形是否仍然满足题目条件（中点、垂足、交点应当自动跟着动）。",
                    "2. 选中关键线段，度量 → 长度，与题目给的数值核对。",
                    "3. 如果某一步是直接手画的点而不是构造出来的，删掉重做，否则拖动后会失真。",
                    "",
                ],
            )
        )

    if scene.warnings:
        sections.append(("注意", [f"- 程序说明：{w}" for w in scene.warnings] + [""]))

    out = list(head)
    for i, (sec_title, body) in enumerate(sections):
        out.append(f"## {_CN[i] if i < len(_CN) else i + 1}、{sec_title}")
        out.append("")
        out.extend(body)
    return "\n".join(out).rstrip() + "\n"


def _describe(expr: str, p) -> str:
    args = _args(expr)
    if expr.startswith("Midpoint(") and len(args) == 2:
        return f"选中点 {args[0]}、{args[1]} → 构造 → 中点。（若标签不是 {p.label}，右键 → 属性 改标签）"
    if expr.startswith("ClosestPoint("):
        m = re.match(r"ClosestPoint\(Line\(([A-Z]),([A-Z])\),([A-Z])\)", expr)
        if m:
            line = m.group(1) + m.group(2)
            src = m.group(3)
            return (
                f"选中点 {src} 和线段 {line} → 构造 → 垂线；"
                f"再选中这条垂线与线段 {line} → 构造 → 交点，把交点标签改为 {p.label}。"
            )
    if expr.startswith("Intersect("):
        return f"先画出两条对角线，选中它们 → 构造 → 交点，标签改为 {p.label}。"
    if "*(" in expr:
        return (
            f"直接绘制点 ({fmt(p.x)}, {fmt(p.y)})，或选中线段后 构造 → 线段上的点 再调整位置；"
            f"动态做法：度量线段长度，用「计算」得到比例后在 绘图 → 绘制点 里用度量值定位。"
        )
    return f"按坐标 ({fmt(p.x)}, {fmt(p.y)}) 绘制。"


def _args(expr: str) -> list[str]:
    m = re.match(r"[A-Za-z]+\((.*)\)$", expr)
    if not m:
        return []
    return [a.strip() for a in m.group(1).split(",") if a.strip()]


def write(scene: Scene, path: str, title: str = "") -> str:
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(markdown(scene, title))
    return path
