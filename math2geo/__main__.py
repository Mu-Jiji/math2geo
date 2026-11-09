"""入口：`python -m math2geo` 走命令行，`python -m math2geo gui` 打开图形界面。"""

import sys

from .cli import main as cli_main


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "gui":
        from .gui import main as gui_main

        return gui_main()
    return cli_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
