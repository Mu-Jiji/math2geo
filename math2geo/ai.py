"""模型理解层：读题，输出作图方案 JSON。

只负责“看懂题、给方案”，坐标一律交给 construct.py；任何失败都抛 AIError，
由上层决定怎么提示，不把半成品塞进 Scene。
"""

from __future__ import annotations

import base64
import io
import json
import os
import re
import time
from dataclasses import dataclass
from typing import Any

DEFAULT_BASE = "https://api.deepseek.com/v1"
DEFAULT_MODEL = "deepseek-flash"
DEFAULT_TIMEOUT = 120.0
DEFAULT_MAX_TOKENS = 8000

_PROMPT_PATH = os.path.join(os.path.dirname(__file__), "templates", "plan_prompt.txt")


class AIError(RuntimeError):
    """云端理解失败。"""


@dataclass
class AIConfig:
    api_key: str
    base_url: str = DEFAULT_BASE
    model: str = DEFAULT_MODEL
    timeout: float = DEFAULT_TIMEOUT
    max_tokens: int = DEFAULT_MAX_TOKENS
    temperature: float = 0.1
    effort: str = "low"

    @property
    def endpoint(self) -> str:
        base = self.base_url.rstrip("/")
        if base.endswith("/chat/completions"):
            return base
        return base + "/chat/completions"


# ------------------------------------------------------------------ 配置


def _snapanswer_config() -> dict:
    """读 SnapAnswer 的配置（用户本机已经配好 key 时直接复用）。"""
    path = os.path.join(os.environ.get("APPDATA", ""), "snapanswer", "config.toml")
    if not path or not os.path.exists(path):
        return {}
    try:
        import tomllib

        with open(path, "rb") as fh:
            return tomllib.load(fh).get("llm", {}) or {}
    except Exception:
        pass
    # 退路：正则粗读
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        out = {}
        for key in ("api_key", "api_key_env", "base_url", "model"):
            m = re.search(rf'(?m)^\s*{key}\s*=\s*"([^"]*)"', text)
            if m:
                out[key] = m.group(1)
        return out
    except Exception:
        return {}


def _looks_like_key(value: str | None) -> bool:
    return bool(value) and len(value) > 20 and " " not in value


def resolve_config(
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
    timeout: float | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
) -> AIConfig | None:
    key = api_key or os.environ.get("MATH2GEO_API_KEY") or os.environ.get("DEEPSEEK_API_KEY")
    base = base_url or os.environ.get("MATH2GEO_BASE_URL")
    mdl = model or os.environ.get("MATH2GEO_MODEL")
    tmo = timeout or (
        float(os.environ["MATH2GEO_TIMEOUT"]) if os.environ.get("MATH2GEO_TIMEOUT", "").replace(".", "", 1).isdigit() else None
    )

    if not key:
        conf = _snapanswer_config()
        for cand in (conf.get("api_key_env"), conf.get("api_key")):
            if _looks_like_key(cand):
                key = str(cand)
                break
        if not key and _looks_like_key(os.environ.get("OPENAI_API_KEY")):
            key = os.environ["OPENAI_API_KEY"]
        if not mdl and conf.get("model"):
            mdl = str(conf["model"])
        if not base and conf.get("base_url"):
            base = str(conf["base_url"])

    if not key:
        return None
    return AIConfig(
        api_key=key,
        base_url=(base or DEFAULT_BASE).rstrip("/"),
        model=mdl or DEFAULT_MODEL,
        timeout=float(tmo or DEFAULT_TIMEOUT),
        max_tokens=int(max_tokens or DEFAULT_MAX_TOKENS),
        temperature=float(temperature if temperature is not None else 0.1),
        effort=os.environ.get("MATH2GEO_EFFORT") or "low",
    )


def unavailable_reason() -> str:
    return (
        "没有找到可用的 API key：设置环境变量 MATH2GEO_API_KEY（或 DEEPSEEK_API_KEY），"
        "或用 --ai-key 传入。"
    )


# ------------------------------------------------------------------ 请求


def _read_prompt() -> str:
    try:
        with open(_PROMPT_PATH, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return "你是数学作图助手，读题后输出作图方案 JSON。"


def _image_data_url(path: str, max_side: int = 1800) -> str:
    try:
        from PIL import Image

        with Image.open(path) as im:
            im = im.convert("RGB")
            if max(im.size) > max_side:
                im.thumbnail((max_side, max_side), Image.LANCZOS)
            buf = io.BytesIO()
            im.save(buf, "JPEG", quality=88)
            raw = buf.getvalue()
    except Exception:
        with open(path, "rb") as fh:
            raw = fh.read()
    return "data:image/jpeg;base64," + base64.b64encode(raw).decode()


def _build_messages(
    prompt: str,
    image: str | None,
    text: str | None,
    ocr_text: str | None,
    instructions: str | None = None,
) -> list[dict]:
    parts: list[str] = []
    if text:
        parts.append("题目文字（用户提供）：\n" + text.strip())
    if ocr_text and (not text or ocr_text.strip() != text.strip()):
        parts.append(
            "本地 OCR 的参考文本（可能有错，仅用于对照，以照片为准）：\n" + ocr_text.strip()
        )
    if instructions:
        parts.append("额外要求（按用户设置）：\n" + instructions.strip())
    parts.append("请按系统提示的格式输出作图方案 JSON。")

    content: list[dict] = [{"type": "text", "text": "\n\n".join(parts)}]
    if image:
        content.append({"type": "image_url", "image_url": {"url": _image_data_url(image), "detail": "high"}})
    return [
        {"role": "system", "content": prompt},
        {"role": "user", "content": content},
    ]


def _post(cfg: AIConfig, messages: list[dict], max_tokens: int) -> tuple[dict, float]:
    import requests

    body = {
        "model": cfg.model,
        "messages": messages,
        "temperature": cfg.temperature,
        "max_tokens": max_tokens,
        "reasoning_effort": cfg.effort,
        "response_format": {"type": "json_object"},
    }
    t0 = time.time()
    try:
        resp = requests.post(
            cfg.endpoint,
            headers={"Authorization": f"Bearer {cfg.api_key}", "Content-Type": "application/json"},
            json=body,
            timeout=cfg.timeout,
        )
    except Exception as exc:  # noqa: BLE001
        raise AIError(f"连接模型服务失败：{exc}") from exc
    elapsed = time.time() - t0

    if resp.status_code != 200:
        snippet = resp.text[:300].replace("\n", " ")
        raise AIError(f"模型返回 {resp.status_code}：{snippet}")
    try:
        return resp.json(), elapsed
    except ValueError as exc:
        raise AIError("模型返回的不是 JSON 响应") from exc


_LATEX_WORDS = (
    "frac dfrac tfrac sqrt triangle angle angle odot pi alpha beta gamma theta lambda mu "
    "varphi omega Delta cdot times div pm infty le leq ge geq ne neq approx parallel perp "
    "in notin subset cup cap emptyset therefore because Rightarrow Leftrightarrow sim cong "
    "degree circ sin cos tan cot ln log max min left right displaystyle text mathrm mathbb "
    "quad qquad partial sum int overline vec"
).split()


def _repair_escapes(s: str) -> str:
    """模型爱在 JSON 字符串里写 LaTeX（\\( \\dfrac），那不是合法 JSON 转义。

    只把「反斜杠 + 已知的 LaTeX 命令名」补成双反斜杠，避免把真正的 \\n 弄坏。
    """
    pattern = r"(?<!\\)\\(" + "|".join(sorted(_LATEX_WORDS, key=len, reverse=True)) + r")(?![a-zA-Z])"
    s = re.sub(pattern, r"\\\\\1", s)
    # 数学定界符和换行符
    s = s.replace("\\(", "\\\\(").replace("\\)", "\\\\)")
    s = s.replace("\\[", "\\\\[").replace("\\]", "\\\\]")
    return s


def _extract_json(text: str) -> dict:
    s = text.strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z]*\s*", "", s)
        s = re.sub(r"\s*```$", "", s).strip()

    candidates: list[str] = [s]
    start = s.find("{")
    end = s.rfind("}")
    if start >= 0 and end > start:
        candidates.append(s[start : end + 1])

    for raw in candidates:
        for candidate in (raw, re.sub(r",\s*([}\]])", r"\1", raw), _repair_escapes(raw), _repair_escapes(re.sub(r",\s*([}\]])", r"\1", raw))):
            try:
                data = json.loads(candidate)
                if isinstance(data, dict):
                    return data
            except json.JSONDecodeError:
                continue
    raise AIError("模型输出的不是合法 JSON：" + s[:160].replace("\n", " "))


def understand(
    image: str | None = None,
    text: str | None = None,
    ocr_text: str | None = None,
    cfg: AIConfig | None = None,
    instructions: str | None = None,
    prompt: str | None = None,
    dimension: str = "2D",
    log=None,
) -> tuple[dict, dict]:
    """读题并返回 (作图方案, 元信息)。失败抛 AIError。"""
    cfg = cfg or resolve_config()
    if cfg is None:
        raise AIError(unavailable_reason())

    prompt = prompt or _read_prompt()
    if str(dimension).upper() == "3D":
        prompt += (
            "\n\n## 三维模式（必须遵守）\n"
            "- 这是一道空间立体几何题；坐标轴为右手系，z 轴垂直向上。\n"
            "- points 里每个自由点都必须同时给出 x、y、z 三个数，不要只给 x、y。\n"
            "- 图形要放在 z≥0 的空间里；底面、顶点、中点等按真实空间关系给坐标。\n"
            "- 线段仍用两端点表示；需要截面的平面会由程序按用户设置的方向生成，不需要你输出。\n"
            "- 必须把立体图形的所有可见面都写进 polygons（每个面一组点，fill 设为 true），不要只给线段。"
        )
    messages = _build_messages(prompt, image, text, ocr_text, instructions)

    budget = cfg.max_tokens
    last_err: Exception | None = None
    for attempt in range(2):
        try:
            data, elapsed = _post(cfg, messages, budget)
        except AIError as exc:
            last_err = exc
            if attempt == 0 and "连接" in str(exc):
                time.sleep(2.0)
                continue
            raise

        choice = (data.get("choices") or [{}])[0]
        msg = choice.get("message") or {}
        content = (msg.get("content") or "").strip()
        finish = choice.get("finish_reason")

        if not content:
            reasoning = msg.get("reasoning_content") or ""
            if attempt == 0 and (finish == "length" or reasoning):
                budget = min(budget * 2, 32000)
                if log:
                    log("思考过程把输出预算用完了，扩大预算重试…")
                continue
            raise AIError("模型没有给出作图方案（只返回了思考过程）")

        try:
            plan = _extract_json(content)
        except AIError as exc:
            # 输出被截断（finish=length）或 JSON 不完整时，扩大预算再要一次
            if attempt == 0 and (finish == "length" or not content.rstrip().endswith("}")):
                budget = min(budget * 2, 32000)
                if log:
                    log("方案 JSON 不完整，扩大输出预算重试…")
                continue
            raise AIError(str(exc)) from exc

        meta = {
            "model": data.get("model") or cfg.model,
            "elapsed": round(elapsed, 1),
            "usage": data.get("usage") or {},
            "finish": finish,
        }
        return plan, meta

    raise AIError(f"多次尝试仍失败：{last_err}")


def understand_text(text: str, cfg: AIConfig | None = None, log=None) -> tuple[dict, dict]:
    return understand(image=None, text=text, cfg=cfg, log=log)
