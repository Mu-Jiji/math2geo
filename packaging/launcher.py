"""打包入口：无参数时直接打开图形界面，带参数时交给命令行。"""

from __future__ import annotations

import os
import sys


def _main() -> int:
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("MuJiji.Math2Geo")
    except Exception:
        pass

    args = sys.argv[1:]

    if args == ["--smoke"]:
        from PySide6.QtWidgets import QApplication

        from math2geo.gui import MainWindow

        app = QApplication([])
        win = MainWindow()
        marker = os.path.join(os.environ.get("TEMP", "."), "math2geo_smoke.txt")
        with open(marker, "w", encoding="utf-8") as fh:
            fh.write(f"pages={win.stack.count()} title={win.title_movie is not None}\n")
        win.close()
        return 0

    if not args or args[0] in ("gui", "--gui"):
        from math2geo.gui import main as gui_main

        return gui_main()

    from math2geo.__main__ import main as cli_main

    return cli_main(args)


if __name__ == "__main__":
    raise SystemExit(_main())
