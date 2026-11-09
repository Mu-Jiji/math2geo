"""OCR 文本的归一化：全角/符号/数学记号统一，为后续正则解析做准备。"""

from __future__ import annotations

import re

# 全角 ASCII（！到 ～）逐个映射到半角；str.translate 的键必须是码位整数
_FULLWIDTH = {0xFF01 + i: chr(0x21 + i) for i in range(94)}
_FULLWIDTH[0x3000] = " "

_PUNCT = {
    "，": ",",
    "；": ";",
    "：": ":",
    "（": "(",
    "）": ")",
    "、": ",",
    "？": "?",
    "！": "!",
    "【": "[",
    "】": "]",
    "《": "<",
    "》": ">",
    "“": '"',
    "”": '"',
    "‘": "'",
    "’": "'",
}

_SUP = {
    "⁰": "0", "¹": "1", "²": "2", "³": "3", "⁴": "4",
    "⁵": "5", "⁶": "6", "⁷": "7", "⁸": "8", "⁹": "9",
}
_SUB = {
    "₀": "0", "₁": "1", "₂": "2", "₃": "3", "₄": "4",
    "₅": "5", "₆": "6", "₇": "7", "₈": "8", "₉": "9",
}

# 常见的 OCR/输入法符号变体
_SYMBOLS = [
    ("∆", "△"),
    ("▲", "△"),
    ("⊿", "△"),
    ("☉", "⊙"),
    ("⨀", "⊙"),
    ("○", "⊙"),  # 仅在 ⊙O 语义下合理，后面会再校正
    ("‖", "∥"),
    ("//", "∥"),
    ("⊥", "⊥"),
    ("·", "·"),
    ("∗", "*"),
    ("﹣", "-"),
    ("−", "-"),
    ("–", "-"),
    ("—", "-"),
]

_DEGREE = ["º", "˚"]


def normalize(text: str) -> str:
    """把一段 OCR 结果变成便于正则解析的规范文本。"""
    t = text.replace("\r\n", "\n").replace("\r", "\n")
    t = t.translate(_FULLWIDTH)
    for a, b in _PUNCT.items():
        t = t.replace(a, b)
    for a, b in _SYMBOLS:
        t = t.replace(a, b)

    # 度数符号：º / ˚ -> °，只在数字后把“度”换成 °（避免“角度”被误伤）
    for d in _DEGREE:
        t = t.replace(d, "°")
    t = re.sub(r"(?<=\d)\s*度", "°", t)
    # “∠C=90。” 这种把 ° 认成句号的情况
    t = re.sub(r"(∠\s*[A-Z]\s*=\s*\d{1,3})\s*[。.]", r"\1°", t)

    # 上标/下标还原成 ^n / _n（几何题里 x²、r² 很常见）
    t = "".join("^" + _SUP[c] if c in _SUP else c for c in t)
    t = "".join("_" + _SUB[c] if c in _SUB else c for c in t)
    t = t.replace("^°", "°")

    # ΔABC 里的 Δ 当成三角形（避免误伤判别式 Δ，仅在三字母前转换）
    t = re.sub(r"Δ(?=\s*[A-Z]{3})", "△", t)

    # Rt△ / RT△ / Rt.△
    t = re.sub(r"[Rr]\s*[Tt]\s*\.?\s*(?=△)", "Rt", t)
    # OCR 把 Rt△ABC 认成 RtABC / RtAABC（△ 被识成 A）
    t = re.sub(r"Rt\s*△?\s*([A-Z]{3})(?![A-Z])", r"Rt△\1", t)
    t = re.sub(r"Rt([A-Z])([A-Z]{3})(?![A-Z])", r"Rt△\2", t)
    # ∠ 被认成 L：LC=90 -> ∠C=90
    t = re.sub(r"(?<![A-Za-z])L([A-Z])\s*=\s*(\d{1,3})", r"∠\1=\2", t)

    # 圆 O、三角形 abc 之类的小写标签纠正
    t = re.sub(r"⊙\s*([a-z])\b", lambda m: "⊙" + m.group(1).upper(), t)
    # OCR 常把字母 O 认成数字 0：⊙0 / 圆心0 / 点0
    t = re.sub(r"⊙\s*[0o](?![0-9])", "⊙O", t)
    t = re.sub(r"圆心\s*0", "圆心O", t)
    t = re.sub(r"点\s*0(?![0-9])", "点O", t)
    t = re.sub(r"△\s*([a-z]{3})\b", lambda m: "△" + m.group(1).upper(), t)
    t = re.sub(r"([A-Z])\s*=\s*([a-z])\s*([A-Z])", lambda m: f"{m.group(1)}={m.group(2).upper()}{m.group(3)}", t)

    # 空格整理：中文之间的空格是 OCR 噪声
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"(?<=[\u4e00-\u9fff]) +", "", t)
    t = re.sub(r" +(?=[\u4e00-\u9fff])", "", t)
    t = re.sub(r" +(?=[,;:.°])", "", t)
    t = re.sub(r"(?<=[=+\-*/^(]) +", "", t)
    t = re.sub(r" +(?=[=+\-*/^)])", "", t)
    t = re.sub(r"\n{2,}", "\n", t)
    return t.strip()


def normalize_expr(expr: str) -> str:
    """把函数表达式整理成 GeoGebra 能直接吃的形式。"""
    s = expr.strip()
    s = s.translate(_FULLWIDTH)
    s = s.replace("×", "*").replace("÷", "/").replace("−", "-").replace("–", "-")
    s = s.replace("（", "(").replace("）", ")")
    s = s.replace(" ", "")
    # 去掉结尾的“求…”“则…”等中文尾巴
    s = re.split(r"[\u4e00-\u9fff]", s)[0]
    # x2 -> x^2（OCR 常见的丢失上标）；仅处理字母后紧跟单个数字
    s = re.sub(r"(?<=[a-zA-Z])(\d)(?![\d.])", r"^\1", s)
    s = re.sub(r"\^\{?(\d)\}?", r"^\1", s)
    # 补上省略的乘号：4x -> 4*x，3(x+1) -> 3*(x+1)
    s = re.sub(r"(?<=[0-9)])(?=[a-zA-Z(])", "*", s)
    s = s.strip(" ,;.")
    s = re.sub(r"\^+", "^", s)
    return s


def split_clauses(text: str) -> list[str]:
    """按句号/分号/换行切句，用于统计“哪些话没认出来”。"""
    parts = re.split(r"[。;；\n]", text)
    return [p.strip(" ,.") for p in parts if p.strip(" ,.")]


def looks_like_function(expr: str) -> bool:
    if "x" not in expr:
        return False
    return bool(re.fullmatch(r"[0-9xX+\-*/^().]+", expr.replace(" ", "")))


# ------------------------------------------------------------------ LaTeX -> 纯文本

_LATEX_CMDS = {
    r"\triangle": "△", r"\angle": "∠", r"\odot": "⊙", r"\pi": "π",
    r"\alpha": "α", r"\beta": "β", r"\gamma": "γ", r"\theta": "θ", r"\lambda": "λ",
    r"\mu": "μ", r"\varphi": "φ", r"\omega": "ω", r"\Delta": "Δ",
    r"\cdot": "·", r"\times": "×", r"\div": "÷", r"\pm": "±", r"\infty": "∞",
    r"\le": "≤", r"\leq": "≤", r"\ge": "≥", r"\geq": "≥",
    r"\ne": "≠", r"\neq": "≠", r"\approx": "≈", r"\parallel": "∥", r"\perp": "⊥",
    r"\in": "∈", r"\notin": "∉", r"\subset": "⊂", r"\cup": "∪", r"\cap": "∩",
    r"\emptyset": "∅", r"\therefore": "∴", r"\because": "∵",
    r"\Rightarrow": "⇒", r"\Leftrightarrow": "⇔", r"\sim": "∽", r"\cong": "≌",
    r"\degree": "°", r"\circ": "°",
    r"\sin": "sin", r"\cos": "cos", r"\tan": "tan", r"\cot": "cot",
    r"\ln": "ln", r"\log": "log", r"\max": "max", r"\min": "min",
    r"\mathbb": "", r"\mathrm": "", r"\mathbf": "", r"\mathcal": "",
    r"\left": "", r"\right": "", r"\displaystyle": "",
    r"\,": "", r"\;": "", r"\!": "", r"\quad": " ", r"\qquad": "  ",
}



def _read_group(s: str, j: int):
    """从 s[j] 读一个 {...} 或单个记号，返回 (内容, 新位置)。"""
    if j >= len(s):
        return None, j
    if s[j] == "{":
        depth = 0
        k = j
        while k < len(s):
            if s[k] == "{":
                depth += 1
            elif s[k] == "}":
                depth -= 1
                if depth == 0:
                    return s[j + 1 : k], k + 1
            k += 1
        return None, j
    m = re.match(r"[^\s,;)]+", s[j:])
    if not m:
        return None, j
    return m.group(0), j + m.end()


def _expand_frac(s: str) -> str:
    """把 \\frac{a}{b}、\\frac12 这类（含嵌套花括号）展开成 (a)/(b)。"""
    out: list[str] = []
    i = 0
    while i < len(s):
        m = re.match(r"\\[dt]?frac", s[i:])
        if not m:
            out.append(s[i])
            i += 1
            continue
        j = i + m.end()
        while j < len(s) and s[j] == " ":
            j += 1
        num, j2 = _read_group(s, j)
        if num is None:
            out.append(s[i])
            i += 1
            continue
        j = j2
        while j < len(s) and s[j] == " ":
            j += 1
        den, j3 = _read_group(s, j)
        if den is None:
            out.append(s[i])
            i += 1
            continue
        out.append(f"({_expand_frac(num)})/({_expand_frac(den)})")
        i = j3
    return "".join(out)

def to_plain(text: str) -> str:
    """把行内 LaTeX 转成适合 matplotlib / HTML 直接显示的纯文本。"""
    s = text or ""
    # 去掉数学定界符
    s = s.replace("\\(", "").replace("\\)", "").replace("\\[", "").replace("\\]", "")
    s = s.replace("$$", "").replace("$", "")

    s = _expand_frac(s)
    # \frac{a}{b} -> (a)/(b)，支持嵌套一层
    for _ in range(3):
        s = re.sub(r"\\[dt]?frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}", r"(\1)/(\2)", s)
    # \sqrt{x} -> √(x)，\sqrt[n]{x} -> n次√(x)
    s = re.sub(r"\\sqrt\s*\[([^\]]*)\]\s*\{([^{}]*)\}", r"\1√(\2)", s)
    s = re.sub(r"\\sqrt\s*\{([^{}]*)\}", r"√(\1)", s)
    # TeX 简写：\frac12、\sqrt3
    s = re.sub(r"\\[dt]?frac\s*(\d)\s*(\d)", r"\1/\2", s)
    s = re.sub(r"\\sqrt\s*(\d+(?:\.\d+)?)", r"√\1", s)
    s = re.sub(r"\\sqrt\s*([a-zA-Z])", r"√\1", s)
    s = re.sub(r"\\text\s*\{([^{}]*)\}", r"\1", s)

    for cmd, rep in sorted(_LATEX_CMDS.items(), key=lambda kv: -len(kv[0])):
        s = s.replace(cmd, rep)

    # 上标/下标：^{2} -> ^2，_{1} -> _1
    s = re.sub(r"\^\s*\{([^{}]*)\}", r"^\1", s)
    s = re.sub(r"_\s*\{([^{}]*)\}", r"_\1", s)
    s = s.replace("^°", "°")
    # 剩下的花括号直接去掉
    s = s.replace("\\ ", " ").replace("{", "").replace("}", "")
    # △ ABC / ∠ C 中间的空白去掉
    s = re.sub(r"([△∠⊙])\s+", r"\1", s)
    # 反斜杠命令残留：\foo -> foo
    s = re.sub(r"\\([a-zA-Z]+)", r"\1", s)
    # √3 这种单个数字不必要括号
    s = re.sub(r"√\((\d+(?:\.\d+)?)\)", r"√\1", s)
    # 中文与数学符号之间的多余空格
    s = re.sub(r"(?<=[\u4e00-\u9fff]) +(?=[△∠⊙])", "", s)
    s = re.sub(r" +(?=[，。；：、])", "", s)
    s = re.sub(r"(?<=[A-Za-z0-9)]) +(?=[\u4e00-\u9fff])", "", s)
    # 常见平方/立方写得好看一点
    s = re.sub(r"\^2(?!\d)", "²", s)
    s = re.sub(r"\^3(?!\d)", "³", s)
    s = re.sub(r"[ \t]{2,}", " ", s)
    return s.strip()
