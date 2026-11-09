"""从题目到成品的一条龙流程。

题目（图片或文字）先交给模型理解，得到作图方案；坐标由 construct.py 算，
最后统一渲染成预览图、GeoGebra 页面和报告。
"""

from __future__ import annotations

import json
import os
import time

from . import ai as ai_mod
from . import plan as plan_mod, render_ggb, render_sketchpad
from .model import Scene, fmt
from .preview import render as render_preview

_3D_HINTS = (
    "立体", "空间", "棱锥", "棱柱", "正方体", "长方体", "圆锥", "圆柱",
    "三棱锥", "四棱锥", "二面角", "异面", "截面", "体积", "表面积",
    "法向量", "空间直角坐标系", "z轴", "z 轴", "平面ABCD", "平面PAD",
)


def _detect_dimension(text: str | None, image: str | None) -> tuple[str, list[str]]:
    t = text or ""
    hits = [k for k in _3D_HINTS if k in t]
    if hits:
        return "3D", hits
    return "2D", []


def run(
    image: str | None = None,
    text: str | None = None,
    outdir: str = "out",
    title: str | None = None,
    preview: bool = True,
    ai: str | bool = "auto",
    ai_key: str | None = None,
    ai_base: str | None = None,
    ai_model: str | None = None,
    ai_timeout: float | None = None,
    ai_max_tokens: int | None = None,
    ai_temperature: float | None = None,
    plan_file: str | None = None,
    options: dict | None = None,
    log=print,
) -> dict:
    if not image and not (text or "").strip():
        raise ValueError("要么给一张题目照片，要么用 --text 给题干")
    if image and not os.path.exists(image):
        raise FileNotFoundError(image)

    os.makedirs(outdir, exist_ok=True)
    stem = title or (os.path.splitext(os.path.basename(image))[0] if image else "problem")
    opts = dict(DEFAULT_OPTIONS)
    if options:
        opts.update({k: v for k, v in options.items() if v is not None})

    t0 = time.time()
    plan, meta = _get_plan(
        image=image,
        text=text,
        plan_file=plan_file,
        ai=ai,
        ai_key=ai_key,
        ai_base=ai_base,
        ai_model=ai_model,
        ai_timeout=ai_timeout,
        ai_max_tokens=ai_max_tokens,
        ai_temperature=ai_temperature,
        options=opts,
        log=log,
    )
    t_ai = time.time() - t0

    if not isinstance(plan, dict):
        raise ai_mod.AIError("模型返回的作图方案不是 JSON 对象")
    scene = plan_mod.build_scene(plan, problem_text=text or "")
    if not scene.points and not scene.funcs:
        raise ai_mod.AIError("模型没有给出可画的图形")
    t_solve = time.time() - t0 - t_ai

    paths: dict[str, str] = {}

    def _w(key: str, filename: str, content: str) -> None:
        path = os.path.join(outdir, filename)
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(content)
        paths[key] = path

    _w("problem", "problem.txt", (scene.problem_text or text or "").strip() + "\n")
    _w("plan", "plan.json", json.dumps(plan, ensure_ascii=False, indent=2) + "\n")
    _w("scene", "scene.json", scene.to_json() + "\n")

    paths.update(render_ggb.write(scene, outdir, stem=stem, style=opts))
    paths["sketchpad"] = render_sketchpad.write(scene, os.path.join(outdir, "sketchpad_steps.md"), title=stem)
    if preview:
        paths["preview"] = render_preview(
            scene,
            os.path.join(outdir, "preview.png"),
            dpi=int(opts.get("dpi") or 170),
            style=opts,
        )
        if str(opts.get("extra_format") or "").lower() == "svg":
            svg = os.path.join(outdir, "preview.svg")
            render_preview(scene, svg, style=opts)
            paths["preview_svg"] = svg

    report = build_report(scene, meta, stem=stem, image=image, paths=paths, raw_text=text or "")
    _w("report", "report.md", report)

    return {
        "text": scene.problem_text,
        "scene": scene,
        "paths": paths,
        "warnings": scene.warnings,
        "timing": {"ai": t_ai, "solve": t_solve},
        "stem": stem,
        "meta": meta,
    }


DEFAULT_OPTIONS = {
    "main_color": "#1F5C46",
    "aux_color": "#8FD3A8",
    "aux_dashed": True,
    "axes": False,
    "grid": False,
    "dpi": 170,
    "extra_format": "",
    "offline_bundle": False,
    "include_problem": True,
    "answer_detail": "丰富",
    "show_difficulty": False,
    "show_breakthrough": False,
    "prompt": "",
}


def _instructions(opts: dict) -> str:
    lines = []
    detail = str(opts.get("answer_detail") or "简单")
    if detail == "答案":
        lines.append("只给最终答案，steps 留空数组。")
    elif detail == "丰富":
        lines.append("解答过程给 4~7 步，公式写清楚。")
    if opts.get("show_difficulty"):
        lines.append("在 JSON 里额外输出 difficulty：0 到 1 之间的小数，表示题目难度。")
    if opts.get("show_breakthrough"):
        lines.append("在 JSON 里额外输出 breakthrough：一句话说明解题突破口。")
    return "\n".join(lines)


def _get_plan(image, text, plan_file, ai, ai_key, ai_base, ai_model, ai_timeout,
              ai_max_tokens, ai_temperature, options, log):
    if plan_file:
        try:
            with open(plan_file, encoding="utf-8-sig") as fh:
                plan = json.load(fh)
        except (OSError, ValueError) as exc:
            raise ai_mod.AIError(f"读不了方案文件 {plan_file}：{exc}") from exc
        return plan, {"model": "file", "elapsed": 0.0, "usage": {}}

    token_budget = int(ai_max_tokens or 4000)
    is_3d = str(options.get("dimension") or "2D").upper() == "3D"
    if is_3d:
        try:
            factor = float(options.get("token_factor_3d", 2.5) or 2.5)
        except (TypeError, ValueError):
            factor = 2.5
        factor = max(1.0, min(5.0, factor))
        token_budget = int(round(token_budget * factor))
        log(f"→ 三维模式：token 预算提高到 {token_budget}（{factor:.2f}×）")

    cfg = ai_mod.resolve_config(
        api_key=ai_key,
        base_url=ai_base,
        model=ai_model,
        timeout=ai_timeout,
        max_tokens=token_budget,
        temperature=ai_temperature,
    )
    if cfg is None:
        raise ai_mod.AIError(
            "没有可用的 API key：设置环境变量 MATH2GEO_API_KEY（或 DEEPSEEK_API_KEY），或用 --ai-key 传入。"
        )
    if str(ai).lower() in ("off", "no", "false", "0", "local"):
        raise ai_mod.AIError("这个版本只保留 AI 识别；要么给 --ai，要么配好 key")

    log(f"→ 云端理解：{cfg.model}")
    plan, meta = ai_mod.understand(
        image=image,
        text=text,
        ocr_text=None,
        cfg=cfg,
        instructions=_instructions(options),
        prompt=(options.get("prompt") or None),
        dimension=str(options.get("dimension") or "2D"),
        log=log,
    )
    log(f"  读完题：{meta.get('elapsed')}s，tokens {(meta.get('usage') or {}).get('total_tokens', '?')}")
    return plan, meta


def build_report(scene: Scene, meta: dict, stem: str, image: str | None, paths: dict, raw_text: str = "") -> str:
    out: list[str] = []
    out.append(f"# 作图报告：{stem}")
    out.append("")
    out.append("## 一、题目")
    out.append("")
    out.append("```text")
    out.append(scene.problem_text)
    out.append("```")
    out.append("")
    model = meta.get("model", "?")
    elapsed = meta.get("elapsed", 0)
    tokens = (meta.get("usage") or {}).get("total_tokens")
    bits = [f"模型 {model}"]
    if elapsed:
        bits.append(f"{elapsed}s")
    if tokens:
        bits.append(f"{tokens} tokens")
    out.append("　·　".join(bits))
    out.append("")

    out.append("## 二、题意理解")
    out.append("")
    kind = {
        "plane_geometry": "平面几何",
        "function": "函数与导数",
        "conic": "圆锥曲线",
        "solid": "立体几何",
    }.get(str(scene.meta.get("kind") or ""), str(scene.meta.get("kind") or "图形"))
    out.append(f"- 题型：{kind}")
    if scene.meta.get("understanding"):
        out.append(f"- 理解：{scene.meta['understanding']}")
    if scene.meta.get("difficulty") is not None:
        out.append(f"- 难度系数：{scene.meta['difficulty']:.2f}")
    if scene.meta.get("breakthrough"):
        out.append(f"- 突破点：{scene.meta['breakthrough']}")
    out.append("")

    out.append("## 三、图形对象")
    out.append("")
    if scene.points:
        out.append("| 点 | x | y | 构造方式 |")
        out.append("| --- | --- | --- | --- |")
        for p in scene.points:
            out.append(f"| {p.label} | {fmt(p.x)} | {fmt(p.y)} | {p.dynamic or '自由点'} |")
        out.append("")
    if scene.segments:
        out.append("- 线段：" + "、".join(f"{s.a}{s.b}" for s in scene.segments))
    if scene.lines:
        out.append("- 直线：" + "、".join(f"{l.a}{l.b}" for l in scene.lines))
    for c in scene.circles:
        r = f"R={fmt(c.radius)}" if c.radius is not None else f"过 {c.through}"
        out.append(f"- 圆：⊙{c.center}（{r}）")
    for f in scene.funcs:
        out.append(f"- 函数：{f.name}(x) = {f.expr}")
    out.append("")

    checks = scene.meta.get("checks") or []
    out.append("## 四、题设自检")
    out.append("")
    if checks:
        out.append("| 量 | 题设值 | 画出来的值 | 结果 |")
        out.append("| --- | --- | --- | --- |")
        for c in checks:
            ok = "✓" if c["ok"] else "✗"
            out.append(f"| {c['what']} | {c['want']:g} | {c['got']:g} | {ok} |")
        out.append("")
    else:
        out.append("- 没有可核验的已知量。")
        out.append("")

    answer = (scene.meta.get("answer") or "").strip()
    out.append("## 五、答案")
    out.append("")
    out.append(answer if answer else "- 方案里没有给出答案。")
    out.append("")

    if scene.steps:
        out.append("## 六、思路")
        out.append("")
        for i, s in enumerate(scene.steps, 1):
            body = f"：{s.body}" if s.body else ""
            out.append(f"{i}. **{s.title}**{body}")
        out.append("")

    out.append("## 七、需要人工确认")
    out.append("")
    if scene.warnings:
        for w in scene.warnings:
            out.append(f"- ⚠ {w}")
    else:
        out.append("- 没有。")
    out.append("")

    out.append("## 八、生成的文件")
    out.append("")
    usage = {
        "problem": "整理后的题干",
        "plan": "AI 的原始作图方案（排查用 --plan-file 复用）",
        "scene": "中间表示 JSON",
        "preview": "预览图，先看它",
        "dynamic": "GeoGebra 动态命令",
        "static": "GeoGebra 静态命令",
        "paste": "单行 Execute 版本",
        "html": "浏览器打开即可拖动的 GeoGebra 小程序",
        "sketchpad": "几何画板构造说明",
    }
    for key, desc in usage.items():
        if key in paths:
            out.append(f"- `{os.path.basename(paths[key])}`：{desc}")
    out.append("")

    out.append("## 九、怎么打开")
    out.append("")
    out.append("1. 双击 `" + os.path.basename(paths.get("html", "figure.html")) + "`，浏览器里就是可拖动的图形。")
    out.append("2. 或把 `geogebra_dynamic.txt` 逐行粘进 GeoGebra 输入栏；派生点是依赖式，拖动顶点不会散。")
    out.append("3. 几何画板：照 `sketchpad_steps.md` 的步骤点菜单。")
    out.append("")
    return "\n".join(out)
