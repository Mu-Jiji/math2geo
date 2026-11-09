"""命令行入口：只保留 AI 识别。

    python -m math2geo run 照片.jpg
    python -m math2geo run --text "在△ABC中，AB=5，BC=6，AC=7，M 是 BC 中点"
    python -m math2geo run 照片.jpg -o out/我的题 --title 我的题
"""

from __future__ import annotations

import argparse
import os
import sys

from . import pipeline


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="math2geo", description="拍题 → AI 理解 → GeoGebra / 几何画板 作图")
    sub = p.add_subparsers(dest="cmd")

    r = sub.add_parser("run", help="处理一道题（照片或文字）")
    r.add_argument("input", nargs="?", help="题目照片")
    r.add_argument("--text", help="直接给题干")
    r.add_argument("-o", "--out", default=None, help="输出目录，默认 out/<题目名>")
    r.add_argument("--title", default=None, help="输出文件的基础名")
    r.add_argument("--no-preview", action="store_true", help="不生成预览图")
    r.add_argument("--ai-key", default=None, help="API key（也可用环境变量 MATH2GEO_API_KEY）")
    r.add_argument("--ai-model", default=None, help="模型名，默认 deepseek-flash")
    r.add_argument("--ai-base", default=None, help="API 地址，默认 https://api.deepseek.com/v1")
    r.add_argument("--ai-timeout", type=float, default=None, help="单次请求超时秒数，默认 120")
    r.add_argument("--plan-file", default=None, help="复用之前保存的 plan.json，不再调用模型")
    return p


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and not argv[0].startswith("-") and argv[0] != "run":
        argv = ["run"] + argv
    if not argv:
        _build_parser().print_help()
        return 0

    args = _build_parser().parse_args(argv)
    if args.cmd != "run":
        _build_parser().print_help()
        return 0
    return _run(args)


def _run(args) -> int:
    if not args.input and not args.text:
        print("给一张题目照片，或用 --text 给题干。", file=sys.stderr)
        return 2
    if args.input and not os.path.exists(args.input):
        print(f"找不到文件：{args.input}", file=sys.stderr)
        return 2

    stem = args.title or (os.path.splitext(os.path.basename(args.input))[0] if args.input else "problem")
    outdir = args.out or os.path.join("out", stem)

    print(f"→ 输入：{args.input or '文字'}")
    try:
        result = pipeline.run(
            image=args.input,
            text=args.text,
            outdir=outdir,
            title=stem,
            preview=not args.no_preview,
            ai_key=args.ai_key,
            ai_base=args.ai_base,
            ai_model=args.ai_model,
            ai_timeout=args.ai_timeout,
            plan_file=args.plan_file,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"处理失败：{exc}", file=sys.stderr)
        return 1

    scene = result["scene"]
    print("→ 题干：" + result["text"].replace("\n", " "))
    print(f"→ 图形：{len(scene.points)} 点 · {len(scene.segments)} 线段 · {len(scene.circles)} 圆 · {len(scene.funcs)} 函数")
    if scene.meta.get("understanding"):
        print("→ 理解：" + str(scene.meta["understanding"]))
    checks = scene.meta.get("checks") or []
    for c in checks:
        mark = "✓" if c["ok"] else "✗"
        print(f"   {mark} {c['what']}：题设 {c['want']:g}，画出 {c['got']:g}")
    if scene.warnings:
        print("→ 提示：")
        for w in scene.warnings:
            print("   ! " + w)

    print(f"→ 输出：{outdir}")
    for key in ("preview", "html", "dynamic", "static", "sketchpad", "report"):
        path = result["paths"].get(key)
        if path:
            print(f"   {os.path.basename(path):22s} {path}")
    return 0
