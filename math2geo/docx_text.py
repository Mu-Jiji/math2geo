"""读题目文件：.docx 直接解压 XML，.txt/.md 直接读。"""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET
import zipfile

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_M = "{http://schemas.openxmlformats.org/officeDocument/2006/math}"


def read_text(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".docx":
        return read_docx(path)
    if ext == ".doc":
        raise ValueError("老式 .doc 读不了，请另存为 .docx")
    with open(path, encoding="utf-8-sig", errors="ignore") as fh:
        return fh.read()


def read_docx(path: str) -> str:
    if not zipfile.is_zipfile(path):
        raise ValueError(f"{os.path.basename(path)} 不是有效的 .docx")
    with zipfile.ZipFile(path) as zf:
        try:
            xml = zf.read("word/document.xml")
        except KeyError as exc:
            raise ValueError("docx 里没有 word/document.xml") from exc

    root = ET.fromstring(xml)
    paragraphs: list[str] = []
    for p in root.iter(_W + "p"):
        chunks: list[str] = []
        for node in p.iter():
            if node.tag in (_W + "t", _M + "t"):
                chunks.append(node.text or "")
            elif node.tag == _W + "tab":
                chunks.append("\t")
            elif node.tag in (_W + "br", _W + "cr"):
                chunks.append("\n")
        text = "".join(chunks).strip()
        if text:
            paragraphs.append(text)
    return "\n".join(paragraphs)
