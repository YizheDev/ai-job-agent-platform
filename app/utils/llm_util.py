"""LLM 响应解析工具

从大模型返回的文本中提取 JSON 对象，兼容各种 markdown 代码块格式。
"""

from __future__ import annotations

import json
import re

from app.core.logger import get_logger

logger = get_logger(__name__)

_JSON_BLOCK_RE = re.compile(
    r"```(?:json)?\s*\n?(.*?)\n?\s*```",
    re.DOTALL,
)


def extract_json(text: str) -> dict:
    """从 LLM 响应文本中提取 JSON 对象。

    依次尝试:
      1. 直接解析整段文本
      2. 提取 ```json ... ``` 或 ``` ... ``` 代码块
      3. 正则查找第一个 { ... } 块

    Raises:
        ValueError: 无法提取有效 JSON
    """
    text = text.strip()

    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        pass

    match = _JSON_BLOCK_RE.search(text)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except (json.JSONDecodeError, ValueError):
            pass

    brace_start = text.find("{")
    brace_end = text.rfind("}")
    if brace_start != -1 and brace_end > brace_start:
        try:
            return json.loads(text[brace_start : brace_end + 1])
        except (json.JSONDecodeError, ValueError):
            pass

    raise ValueError(f"无法从 LLM 响应中提取 JSON: {text[:200]}")
