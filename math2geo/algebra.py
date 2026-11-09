"""初等函数的符号处理：文本 → sympy → GeoGebra 表达式，以及单调性分析。

支持：四则运算、乘方、隐式乘号（ax、2x、x(x+1)）、e^x、exp、
ln/lg/log、sin/cos/tan、sqrt、abs/|x|，以及简单的 LaTeX（\\frac、^{}、\\sqrt）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import sympy as sp
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)

_TRANSFORMS = standard_transformations + (implicit_multiplication_application, convert_xor)

VAR = "x"


# ------------------------------------------------------------------ 文本清洗


def _strip_latex(s: str) -> str:
    """把常见的 LaTeX 片段转成普通算式（不追求完整支持）。"""
    s = s.replace("\\left", "").replace("\\right", "")
    s = s.replace("\\cdot", "*").replace("\\times", "*").replace("\\div", "/")
    # \frac{A}{B}（只处理一层，够用）
    for _ in range(3):
        s = re.sub(r"\\frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}", r"((\1)/(\2))", s)
        s = re.sub(r"\\dfrac\s*\{([^{}]*)\}\s*\{([^{}]*)\}", r"((\1)/(\2))", s)
    s = re.sub(r"\\sqrt\s*\{([^{}]*)\}", r"sqrt(\1)", s)
    s = re.sub(r"\\text\s*\{([^{}]*)\}", r"\1", s)
    s = re.sub(r"\^\s*\{([^{}]*)\}", r"^(\1)", s)
    s = s.replace("\\pi", "pi").replace("\\ln", "ln").replace("\\log", "log")
    s = s.replace("{", "(").replace("}", ")")
    return s


def clean_expr(text: str) -> str:
    s = _strip_latex(text)
    s = s.replace("（", "(").replace("）", ")")
    s = s.replace("−", "-").replace("–", "-").replace("—", "-")
    s = s.replace("×", "*").replace("÷", "/").replace("·", "*")
    s = s.replace("²", "^2").replace("³", "^3")
    # |x| -> abs(x)
    for _ in range(3):
        s = re.sub(r"\|([^|]+)\|", r"abs(\1)", s)
    s = re.sub(r"\s+", "", s)
    s = s.replace("＝", "=")
    return s.strip(" .,;:")


def repair_exponents(s: str) -> tuple[str, list[str]]:
    """修 OCR 常见问题：ex -> e^x、e2 -> e^2、x2 -> x^2。"""
    notes: list[str] = []
    # e 后面紧跟单个字母/数字，多半是上标丢了
    new, n = re.subn(r"(?<![a-zA-Z0-9])e([a-zA-Z0-9])(?![a-zA-Z0-9])", r"e^(\1)", s)
    if n:
        notes.append("OCR 里的 e 与后面的字母/数字贴在一起，已按 e 的指数处理，请核对")
    s = new
    # x2 -> x^2（字母后紧跟单个数字）
    new, n = re.subn(r"(?<=[a-zA-Z])(\d)(?![\d.])", r"^\1", s)
    if n:
        notes.append("补上了缺失的指数符号 ^")
    return new, notes


# ------------------------------------------------------------------ 解析


def make_locals(var: str = VAR) -> dict:
    local = {
        "e": sp.E,
        "E": sp.E,
        "pi": sp.pi,
        "ln": sp.log,
        "log": sp.log,
        "lg": lambda v: sp.log(v, 10),
        "exp": sp.exp,
        "sqrt": sp.sqrt,
        "abs": sp.Abs,
        "sin": sp.sin,
        "cos": sp.cos,
        "tan": sp.tan,
    }
    for ch in "abcdefghijklmnopqrstuvwxyz":
        local.setdefault(ch, sp.Symbol(ch))
    local[var] = sp.Symbol(var)
    return local


def to_sympy(text: str, var: str = VAR) -> sp.Expr | None:
    s = clean_expr(text)
    if not s:
        return None
    s, _ = repair_exponents(s)
    try:
        expr = parse_expr(s, local_dict=make_locals(var), transformations=_TRANSFORMS, evaluate=True)
    except Exception:
        return None
    if not isinstance(expr, sp.Expr):
        return None
    return expr


def params_of(expr: sp.Expr, var: str = VAR) -> list[str]:
    return sorted(str(s) for s in expr.free_symbols if str(s) != var)


# ------------------------------------------------------------------ 输出


def to_ggb(expr: sp.Expr, var: str = VAR) -> str:
    """sympy -> GeoGebra。GeoGebra 接受 e^x、ln(x)、abs(x)、sqrt(x)。"""
    s = sp.sstr(expr)
    s = s.replace("**", "^").replace("exp(", "e^(").replace("Abs(", "abs(").replace("log(", "ln(")
    return s


def to_plain(expr: sp.Expr) -> str:
    """给报告/文字框看的写法（同样是 GeoGebra 风格，方便直接粘）。"""
    return to_ggb(expr)


# ------------------------------------------------------------------ 分析


@dataclass
class FuncAnalysis:
    expr: sp.Expr
    derivative: sp.Expr
    second: sp.Expr
    critical: list[sp.Expr] = field(default_factory=list)
    monotonic: list[tuple[str, float | None, float | None]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def analyse(expr: sp.Expr, var: str = VAR, probe: float = 1.0, domain: tuple[float, float] = (-12.0, 12.0)) -> FuncAnalysis:
    x = sp.Symbol(var)
    d = sp.simplify(sp.diff(expr, x))
    d2 = sp.simplify(sp.diff(d, x))
    fa = FuncAnalysis(expr=expr, derivative=d, second=d2)

    # 临界点：能解析就解析，不能就数值找
    crit: list[sp.Expr] = []
    try:
        sols = sp.solve(sp.Eq(d, 0), x)
        crit = [sp.simplify(s) for s in sols if s.is_real is not False]
    except Exception:
        fa.notes.append("导函数零点无法解析求出，改用数值扫描")

    if not crit:
        import numpy as np

        f = sp.lambdify(x, d, "numpy")
        xs = np.linspace(domain[0], domain[1], 4001)
        ys = f(xs)
        for i in range(1, len(xs) - 1):
            if ys[i - 1] * ys[i + 1] < 0:
                crit.append(sp.Float(round(float(xs[i]), 6)))
        fa.notes.append("临界点为数值近似")

    fa.critical = crit

    # 用默认参数值判定增减区间
    subs = {s: probe for s in expr.free_symbols if str(s) != var}
    dnum = sp.lambdify(x, d.subs(subs), "numpy")
    crit_vals: list[float] = []
    for c in crit:
        try:
            val = complex(c.subs(subs))
        except Exception:
            continue
        if abs(val.imag) < 1e-9:
            crit_vals.append(val.real)
    crit_vals.sort()

    # 定义域（ln 要求 x>0 之类），用来把区间裁掉
    try:
        from sympy.calculus.util import continuous_domain

        dom = continuous_domain(expr, x, sp.S.Reals)
    except Exception:
        dom = sp.S.Reals

    edges = [domain[0]] + [v for v in crit_vals if domain[0] < v < domain[1]] + [domain[1]]
    for a, b in zip(edges, edges[1:]):
        lo, hi = a, b
        try:
            seg = sp.Interval(a, b).intersect(dom)
            if seg.is_empty:
                continue
            if isinstance(seg, sp.Interval):
                lo, hi = float(seg.start), float(seg.end)
        except Exception:
            pass
        mid = (lo + hi) / 2
        try:
            import numpy as np

            with np.errstate(all="ignore"):
                slope = float(dnum(mid))
        except Exception:
            continue
        if slope > 1e-9:
            fa.monotonic.append(("增", lo, hi))
        elif slope < -1e-9:
            fa.monotonic.append(("减", lo, hi))
    return fa


def numeric_points(expr: sp.Expr, xs: list[float], params: dict[str, float], var: str = VAR) -> list[float]:
    import numpy as np

    x = sp.Symbol(var)
    subs = {sp.Symbol(k): v for k, v in params.items()}
    f = sp.lambdify(x, expr.subs(subs), "numpy")
    out = []
    with np.errstate(all="ignore"):
        for v in xs:
            try:
                out.append(float(f(v)))
            except Exception:
                out.append(float("nan"))
    return out
