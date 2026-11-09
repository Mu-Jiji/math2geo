"""用本机 Edge（Playwright）真跑 GeoGebra，逐条验证命令是否生效。

    python tools/ggb_check.py out/final_t4/geogebra_dynamic.txt
    python tools/ggb_check.py --scene out/final_t4/scene.json

不需要联网：deployggb.js 已下载到 tools/ 下。
"""

from __future__ import annotations

import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))

_PAGE = """<!DOCTYPE html><html><head><meta charset="utf-8"></head><body>
<div id="ggb"></div>
<script src="deployggb.js"></script>
<script>
window.failed = []; window.ready = false; window.api = null;
const P = {
  appName: 'classic', width: 900, height: 700, showToolBar: false,
  showAlgebraInput: false, showMenuBar: false, showResetIcon: false,
  language: 'zh', appletOnLoad: function (api) { window.api = api; window.ready = true; }
};
new GGBApplet(P, true).inject('ggb');
window.runCmds = function (cmds) {
  const bad = [];
  cmds.forEach(function (c, i) {
    let ok = false;
    try { ok = window.api.evalCommand(c); } catch (e) { ok = false; }
    if (!ok) bad.push([i + 1, c]);
  });
  return bad;
};
</script></body></html>
"""


def check(cmds: list[str], timeout_ms: int = 60000) -> list[tuple[int, str]]:
    from playwright.sync_api import sync_playwright

    tmp = tempfile.mkdtemp(prefix="ggb-check-")
    page_path = os.path.join(tmp, "index.html")
    with open(page_path, "w", encoding="utf-8") as fh:
        fh.write(_PAGE)
    for name in ("deployggb.js",):
        src = os.path.join(HERE, name)
        if os.path.exists(src):
            with open(src, "rb") as fh:
                data = fh.read()
            with open(os.path.join(tmp, name), "wb") as fh:
                fh.write(data)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="msedge", headless=True, args=["--use-gl=swiftshader"])
        page = browser.new_page()
        page.goto("file:///" + page_path.replace("\\", "/"))
        page.wait_for_function("window.ready === true", timeout=timeout_ms)
        bad = page.evaluate("cmds => window.runCmds(cmds)", cmds)
        browser.close()
    return [(int(n), c) for n, c in bad]


def main() -> int:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 2
    if args[0] == "--scene":
        with open(args[1], encoding="utf-8") as fh:
            scene = json.load(fh)
        from math2geo.model import Scene

        sc = Scene.from_dict(scene)
        from math2geo import render_ggb

        cmds = render_ggb.commands(sc, dynamic=True)
    else:
        with open(args[0], encoding="utf-8") as fh:
            cmds = [ln.strip() for ln in fh if ln.strip() and not ln.startswith("#")]

    bad = check(cmds)
    print(f"共 {len(cmds)} 条命令，失败 {len(bad)} 条")
    for n, c in bad:
        print(f"  {n:3d}. {c}")
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
