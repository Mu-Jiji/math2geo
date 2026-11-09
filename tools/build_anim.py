"""生成开启动画与主标题动画（开发用）。

从工作区的 math2geo.svg 出发：
1. 压缩每个动画的 begin 间隔、略缩短 dur，让笔画更连贯；
2. 用 Edge 逐帧截取（30fps），分别产出
   - assets/intro.webp   整张图纸（启动动画）
   - assets/title.webp   仅标题字形（主界面标题动画，透明背景）
   - assets/title_end.png 标题最终帧

用法：
    python tools/build_anim.py [源 svg 路径]
"""

from __future__ import annotations

import pathlib
import re
import sys

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
TMP = pathlib.Path(__import__("tempfile").gettempdir()) / "math2geo_frames"

FPS = 60
DURATION_MS = int(1000 / FPS)
BEGIN_SCALE = 0.45
DUR_SCALE = 0.85
INTRO_END = 4.9
TITLE_START = 2.3
TITLE_END = 4.9

# 2x 像素下的裁切范围（标题字形）
TITLE_CROP = (100, 400, 1645, 675)


def retime(source: pathlib.Path) -> pathlib.Path:
    text = source.read_text(encoding="utf-8")
    text = re.sub(
        r'begin="([0-9.]+)s"',
        lambda m: f'begin="{float(m.group(1)) * BEGIN_SCALE:.2f}s"',
        text,
    )
    text = re.sub(
        r'dur="([0-9.]+)s"',
        lambda m: f'dur="{float(m.group(1)) * DUR_SCALE:.2f}s"',
        text,
    )
    out = ASSETS / "math2geo_intro.svg"
    out.write_text(text, encoding="utf-8")
    return out


def capture(svg: pathlib.Path, start: float, end: float, folder: pathlib.Path, transparent: bool) -> list[pathlib.Path]:
    folder.mkdir(parents=True, exist_ok=True)
    for old in folder.glob("*.png"):
        old.unlink()
    urls = svg.resolve().as_uri()
    paths: list[pathlib.Path] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge")
        page = browser.new_page(viewport={"width": 880, "height": 510}, device_scale_factor=2)
        page.goto(urls)
        page.wait_for_timeout(400)
        hide = (
            'g[clip-path="url(#frameClip)"], svg > rect:first-of-type{display:none}'
            if transparent
            else ""
        )
        page.evaluate(
            """(hide) => {
                const style = document.createElementNS('http://www.w3.org/2000/svg', 'style');
                style.textContent = 'svg{display:block;margin:0}' + hide;
                document.documentElement.appendChild(style);
            }""",
            hide,
        )
        page.evaluate("document.documentElement.pauseAnimations()")
        total = int(round((end - start) * FPS))
        for index in range(total + 1):
            t = start + index / FPS
            page.evaluate("(t) => document.documentElement.setCurrentTime(t)", t)
            page.wait_for_timeout(8)
            path = folder / f"f{index:04d}.png"
            page.screenshot(path=str(path), omit_background=transparent)
            paths.append(path)
        browser.close()
    return paths


def build_intro(frames: list[pathlib.Path]) -> None:
    images = []
    for path in frames:
        img = Image.open(path).convert("RGB")
        img = img.resize((1320, 766), Image.LANCZOS)
        images.append(img)
    images[0].save(
        ASSETS / "intro.webp",
        save_all=True,
        append_images=images[1:],
        duration=DURATION_MS,
        loop=0,
        quality=80,
        method=6,
    )


def build_title(frames: list[pathlib.Path]) -> None:
    images = []
    for path in frames:
        img = Image.open(path).convert("RGBA")
        img = img.crop(TITLE_CROP)
        img = img.resize((1600, int(1600 * img.height / img.width)), Image.LANCZOS)
        images.append(img)
    images[-1].save(ASSETS / "title_end.png")
    images[0].save(
        ASSETS / "title.webp",
        save_all=True,
        append_images=images[1:],
        duration=DURATION_MS,
        loop=0,
        quality=85,
        method=6,
    )
    print("title frame size", images[0].size)


def main() -> int:
    source = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path(
        r"C:\Users\Givet\Documents\deepseek-harness\default-workspace\math2geo.svg"
    )
    if not source.exists():
        print("找不到源 svg：", source)
        return 1
    svg = retime(source)
    print("retimed ->", svg)

    intro_frames = capture(svg, 0, INTRO_END, TMP / "intro", transparent=False)
    build_intro(intro_frames)
    print("intro frames", len(intro_frames))

    title_frames = capture(svg, TITLE_START, TITLE_END, TMP / "title", transparent=True)
    build_title(title_frames)
    print("title frames", len(title_frames))

    for name in ("intro.webp", "title.webp", "title_end.png"):
        path = ASSETS / name
        print(name, path.stat().st_size // 1024, "KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
