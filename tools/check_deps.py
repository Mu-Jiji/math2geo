"""检查 math2geo 的运行依赖与本机环境。

用法：
    python tools/check_deps.py
或双击项目根目录的 check_deps.bat。
"""

from __future__ import annotations

import importlib
import importlib.metadata as md
import json
import os
import platform
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REQ_FILE = os.path.join(ROOT, "requirements.txt")

# (import 名, pip 包名, 最低版本)
REQUIRED = [
    ("numpy", "numpy", "1.24"),
    ("PIL", "pillow", "10.0"),
    ("sympy", "sympy", "1.12"),
    ("matplotlib", "matplotlib", "3.7"),
]
OPTIONAL = [
    ("PySide6", "PySide6", "6.6", "图形界面"),
    ("playwright", "playwright", None, "tools/ggb_check.py 无头验证"),
]

FILES = [
    "requirements.txt",
    "README.md",
    "assets/icon.png",
    "assets/intro.webp",
    "assets/title.webp",
    "assets/title_end.png",
    "math2geo/templates/plan_prompt.txt",
    "math2geo/templates/figure.html",
    "tools/deployggb.js",
    "tools/ggb_check.py",
]


def _version(dist: str) -> str:
    try:
        return md.version(dist)
    except Exception:
        return "?"


def _tuple(value: str) -> tuple[int, ...]:
    parts: list[int] = []
    for chunk in value.replace("-", ".").split("."):
        digits = "".join(ch for ch in chunk if ch.isdigit())
        if digits:
            parts.append(int(digits))
        else:
            break
    return tuple(parts)


def _ok(installed: str, minimum: str | None) -> bool:
    if not minimum or installed == "?":
        return True
    return _tuple(installed) >= _tuple(minimum)


def check_modules(items) -> tuple[int, int]:
    passed = 0
    for entry in items:
        module, dist, minimum = entry[0], entry[1], entry[2]
        try:
            importlib.import_module(module)
            version = _version(dist)
            good = _ok(version, minimum)
            mark = "OK" if good else "版本过低"
            need = f" (需要 >= {minimum})" if minimum else ""
            print(f"  [{mark}] {dist:12} {version}{need}")
            passed += 1 if good else 0
        except Exception as exc:
            reason = str(exc).splitlines()[0] if str(exc) else exc.__class__.__name__
            print(f"  [缺失] {dist:12} {reason}")
    return passed, len(items)


def check_python() -> bool:
    version = sys.version.split()[0]
    good = sys.version_info >= (3, 10)
    print(f"Python {version}  {'OK' if good else '需要 3.10+'}")
    print(f"解释器 {sys.executable}")
    print(f"系统   {platform.platform()}")
    return good


def check_files() -> tuple[int, int]:
    passed = 0
    for rel in FILES:
        path = os.path.join(ROOT, rel)
        exists = os.path.exists(path)
        print(f"  [{'OK' if exists else '缺失'}] {rel}")
        passed += 1 if exists else 0
    return passed, len(FILES)


def check_key() -> None:
    for name in ("MATH2GEO_API_KEY", "DEEPSEEK_API_KEY"):
        if os.environ.get(name):
            print(f"  [OK] 环境变量 {name}")
            return
    cfg = os.path.join(os.environ.get("APPDATA", ""), "math2geo", "config.json")
    if not os.path.exists(cfg):
        print("  [提示] 未找到 API Key（环境变量 / GUI 配置都没有）")
        return
    try:
        with open(cfg, encoding="utf-8") as fh:
            model = (json.load(fh) or {}).get("model") or {}
        key_env = model.get("key_env") or ""
        if model.get("api_key") or (key_env and os.environ.get(key_env)):
            print("  [OK] GUI 配置里的 API Key")
        elif key_env:
            print(f"  [提示] 配置引用了环境变量 {key_env}，但它当前为空")
        else:
            print("  [提示] 配置文件存在，但还没填 API Key")
    except Exception as exc:
        print(f"  [警告] 配置文件读取失败：{exc}")


def check_edge() -> None:
    paths = [
        os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
    ]
    found = next((p for p in paths if os.path.exists(p)), "")
    print(f"  [{'OK' if found else '提示'}] Edge {'已找到' if found else '未找到（只影响 ggb_check）'}")


def main() -> int:
    print("=" * 52)
    print(" Math2Geo 依赖检查")
    print("=" * 52)

    py_ok = check_python()

    print("\n必需依赖")
    req_ok, req_total = check_modules(REQUIRED)

    print("\n可选依赖")
    opt_ok, opt_total = check_modules(OPTIONAL)

    print("\n项目文件")
    file_ok, file_total = check_files()

    print("\nAPI Key")
    check_key()

    print("\nGeoGebra 验证工具")
    check_edge()

    print("\n" + "-" * 52)
    all_ok = py_ok and req_ok == req_total and file_ok == file_total
    print(f"必需依赖 {req_ok}/{req_total}，可选依赖 {opt_ok}/{opt_total}，文件 {file_ok}/{file_total}")
    if all_ok:
        print("结论：可以运行。启动界面： python -m math2geo gui")
        return 0
    print("结论：缺少必需项，请先运行 install.bat 或查看上面的 [缺失]。")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
