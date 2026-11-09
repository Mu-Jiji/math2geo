"""最小回归测试：构图原语 / 方案转场景 / AI JSON 容错 / 预览渲染。

    python tests/run_tests.py
"""

from __future__ import annotations

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:  # Windows 控制台默认 GBK，测试里有 ² 之类的字符
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from math2geo import plan as plan_mod, render_ggb  # noqa: E402

failures: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        print(f"  ok   {name}")
    else:
        print(f"  FAIL {name} {detail}")
        failures.append(name)


def approx(a: float, b: float, tol: float = 1e-6) -> bool:
    return abs(a - b) <= tol


def test_construct() -> None:
    print("[构图原语]")
    from math2geo import construct as C

    pts = {"A": (0.0, 0.0), "B": (6.0, 0.0), "C": (0.0, 8.0)}
    mx, my = C.evaluate("midpoint", ["A", "B"], pts)
    check("中点", approx(mx, 3.0) and approx(my, 0.0))

    fx, fy = C.evaluate("foot", ["C", "A", "B"], pts)
    check("垂足", approx(fx, 0.0) and approx(fy, 0.0))

    ox, oy = C.evaluate("circumcenter", ["A", "B", "C"], pts)
    check("外心", approx(ox, 3.0) and approx(oy, 4.0))

    tri = {"A": (0.0, 0.0), "B": (6.0, 0.0), "C": (1.0, 4.0)}
    dx, dy = C.evaluate("bisector_foot", ["C", "A", "B"], tri)
    ad, db = math.hypot(dx, dy), math.hypot(6.0 - dx, dy)
    check("角平分线定理", approx(ad / db, math.hypot(1, 4) / math.hypot(5, 4), 1e-9))

    check("GeoGebra 依赖式", C.ggb_expr("midpoint", ["A", "B"]) == "Midpoint(A,B)")


T4_PLAN = {
    "problem_text": "在△ABC中，c·cosB+√3·c·sinB=a+b。(1)求角C；(2)c=√3，CD 平分∠C 交 AB 于 D，求 CD 最大值。",
    "kind": "plane_geometry",
    "understanding": "等边三角形 ABC，作角平分线 CD",
    "answer": "C=60°，CD 最大值 3/2",
    "points": [
        {"name": "A", "x": 0, "y": 0},
        {"name": "B", "x": 1.7320508, "y": 0},
        {"name": "C", "x": 0.8660254, "y": 1.5},
        {"name": "D", "construct": "bisector_foot", "args": ["C", "A", "B"]},
    ],
    "segments": [["A", "B"], ["B", "C"], ["C", "A"], ["C", "D"]],
    "angles": [{"a": "A", "vertex": "C", "b": "B", "label": "60°"}],
    "checks": [
        {"type": "angle", "vertex": "C", "arms": ["A", "B"], "value": 60},
        {"type": "length", "of": ["A", "B"], "value": 1.7320508},
    ],
    "steps": [{"title": "先求角 C", "body": "由正弦定理化边为角。"}],
}


def test_plan() -> None:
    print("[作图方案 -> 场景]")
    sc = plan_mod.build_scene(T4_PLAN)
    check("点齐全", {"A", "B", "C", "D"} <= {p.label for p in sc.points})

    d = sc.point("D")
    ax, ay = sc.coord("A")
    bx, by = sc.coord("B")
    cross = (d.x - ax) * (by - ay) - (d.y - ay) * (bx - ax)
    check("D 在 AB 上", abs(cross) < 1e-9)
    check("D 是依赖式", bool(d.dynamic) and "AngleBisector" in d.dynamic)

    checks = sc.meta.get("checks") or []
    check("自检全部通过", checks and all(c["ok"] for c in checks), str(checks))

    dyn = render_ggb.commands(sc, dynamic=True)
    sta = render_ggb.commands(sc, dynamic=False)
    check("动态命令含角平分线", any("AngleBisector" in c for c in dyn))
    check("静态版无依赖构造", not any("AngleBisector" in c for c in sta))

    bad = dict(T4_PLAN, checks=[{"type": "length", "of": ["A", "B"], "value": 5}])
    check("不一致报警", any("自检不一致" in w for w in plan_mod.build_scene(bad).warnings))

    aux = {
        "points": [
            {"name": "A", "x": 0, "y": 0},
            {"name": "B", "x": 4, "y": 0},
            {"name": "S", "construct": "slope_point", "args": ["A", 2]},
            {"name": "C", "construct": "line_circle", "args": ["A", "S", "A", 1, 0]},
        ]
    }
    sc2 = plan_mod.build_scene(aux)
    s = sc2.point("S")
    check("辅助点不显示", s is not None and s.role == "auxiliary" and not s.show_label)

    # GeoGebra 里 Element(Intersect(...)) 不成立（Intersect 返回点不是列表），必须用带下标的写法
    cmds = render_ggb.commands(sc2)
    cc = next((c for c in cmds if c.startswith("C=")), "")
    check("圆交点用带下标的 Intersect", "Intersect(" in cc and ",1)" in cc and "Element(" not in cc, cc)


def test_ai_json() -> None:
    print("[AI 返回 JSON 容错]")
    from math2geo.ai import _extract_json

    raw = '```json\n{"problem_text": "在 \\\\(\\\\triangle ABC\\\\) 中", "points": []}\n```'
    check("剥 code fence", _extract_json(raw).get("problem_text", "").startswith("在"))

    bad = '{"problem_text": "\\(x\\) 与 \\frac{1}{2}", "kind": "function"}'
    check("修复 LaTeX 转义", "frac" in _extract_json(bad).get("problem_text", ""))

    try:
        _extract_json("no json")
        check("非法输入报错", False)
    except Exception:
        check("非法输入报错", True)


def test_to_plain() -> None:
    print("[LaTeX -> 纯文本]")
    from math2geo.textnorm import to_plain

    s = to_plain(r"在 \(\triangle ABC\) 中，\(\angle C=60^\circ\)，\(c=\sqrt{3}\)，\(x\in\mathbb{R}\)")
    check("符号还原", "△ABC" in s and "∠C=60°" in s and "c=√3" in s and "∈R" in s, s)
    check("没有反斜杠", "\\" not in s, s)


def test_preview() -> None:
    print("[预览渲染]")
    import tempfile

    from math2geo.preview import render

    tmp = tempfile.mkdtemp(prefix="math2geo-preview-")
    sc = plan_mod.build_scene(T4_PLAN)
    path = render(sc, os.path.join(tmp, "geo.png"))
    check("几何预览生成", os.path.exists(path) and os.path.getsize(path) > 10_000)

    fn = {
        "problem_text": "已知 f(x)=x^2-4x+3",
        "kind": "function",
        "functions": [{"name": "f", "expr": "x^2-4x+3", "xmin": -2, "xmax": 6}],
    }
    sc2 = plan_mod.build_scene(fn)
    path2 = render(sc2, os.path.join(tmp, "func.png"))
    check("函数预览生成", os.path.exists(path2) and os.path.getsize(path2) > 10_000)


def test_pipeline() -> None:
    print("[整条流水线（复用方案）]")
    import json
    import tempfile

    from math2geo import pipeline

    tmp = tempfile.mkdtemp(prefix="math2geo-pipe-")
    plan_path = os.path.join(tmp, "plan.json")
    with open(plan_path, "w", encoding="utf-8") as fh:
        json.dump(T4_PLAN, fh, ensure_ascii=False)

    out = os.path.join(tmp, "out")
    res = pipeline.run(text=T4_PLAN["problem_text"], plan_file=plan_path, outdir=out, title="t", log=lambda *_: None)
    for key in ("preview", "html", "dynamic", "static", "sketchpad", "report", "plan", "scene"):
        check(f"产物 {key}", key in res["paths"] and os.path.exists(res["paths"][key]))


def test_gui() -> None:
    print("[图形界面]")
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("MATH2GEO_NO_WINDOW_STATE", "1")
    try:
        from PySide6.QtWidgets import QApplication
    except Exception:
        check("PySide6 未安装（跳过）", True)
        return

    from PySide6.QtWidgets import QLabel

    from math2geo.gui import MainWindow

    app = QApplication.instance() or QApplication([])
    win = MainWindow()
    check("五个页面", win.stack.count() == 5)
    check("主题主色", win.cfg["draw"]["main"].upper() == "#1F5C46")
    check("默认云端", win.cfg["model"]["mode"] == "cloud")

    check("动画开关", hasattr(win, "chk_anim_startup") and hasattr(win, "chk_anim_title"))
    check("标题动画资源", win.title_movie is not None and win.title_movie.isValid())
    check(
        "动画倍速",
        win.cmb_anim_speed.count() == 5
        and 0.5 <= float(win._collect()["other"]["anim_speed"]) <= 2.0,
    )
    check("主题选项", win.theme_combo.count() == 3)
    check("免费API隐藏", win.provider_combo.findText("免费 API") < 0 and not win.free_panel.isVisible())
    check("环境变量折叠", not win.env_row.isVisible())
    check("用户API入口", hasattr(win, "user_api_btn"))
    from math2geo.api_dialogs import KeypadDialog

    check("密码键盘", KeypadDialog(win).display.maxLength() == 6)
    win.theme_combo.setCurrentIndex(1)
    check(
        "主题切换",
        win.shell.mode == "grid" and win._collect()["other"]["background"] == "grid",
    )
    win.theme_combo.setCurrentIndex(0)

    win.log("测试日志")
    win._add_task({"stem": "t", "paths": {"preview": ""}}, 1.0, 10, "")
    check("任务卡片", len(win.tasks) == 1 and win.task_count.text() == "1")
    win._clear_cache_now()
    check(
        "清空缓存",
        not win.tasks and win.task_count.text() == "0" and win.logbox.toPlainText() == "",
    )
    labels = [lab.text() for lab in win.findChildren(QLabel)]
    check("版权信息", any("Mu-Jiji" in text for text in labels))
    win.close()


def main() -> int:
    test_construct()
    test_plan()
    test_ai_json()
    test_to_plain()
    test_preview()
    test_pipeline()
    test_gui()

    print()
    if failures:
        print(f"失败 {len(failures)} 项：")
        for f in failures:
            print("  -", f)
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
