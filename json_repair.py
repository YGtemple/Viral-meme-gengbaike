"""JSON repair agent — robust JSON extraction with retry logic.

Never raises to the caller — internally retries with multiple strategies,
including re-prompting the LLM to fix its own broken output.
"""

import json
import re

from memeclaw.config import config


JSON_FIX_SYSTEM_PROMPT = """你是 JSON 格式修复专家。你的任务是把格式有问题的 JSON 修复为合法 JSON。

规则：
1. 只输出修复后的合法 JSON，不要任何其他文字
2. 保持原始内容和结构不变，只修复格式问题
3. 常见修复：补逗号、去尾逗号、转义内部双引号、转义控制字符
4. 如果内容本身不完整或无法理解，输出 {}

只输出 JSON，不要 markdown 代码块。"""


class JSONRepairAgent:
    """Handles JSON format issues with escalating repair strategies.

    Strategy order:
      1. Direct parse (json_repair library → hand-rolled repair)
      2. Re-prompt LLM to fix its own broken output (up to max_retries times)
    """

    def __init__(self, llm_client=None):
        self.llm = llm_client

    async def extract_with_retry(self, text: str, max_retries: int = 2) -> dict:
        """Extract JSON from LLM output. Never raises — returns {} on total failure."""
        if not text or not text.strip():
            return {}

        # Strategy 1: direct extraction
        result = extract_json(text)
        if result:
            return result

        # Strategy 2+: re-prompt LLM to fix
        for attempt in range(max_retries):
            if self.llm is None:
                break
            try:
                fixed_text = await self._ask_llm_to_fix(text)
                if not fixed_text or not fixed_text.strip():
                    continue
                result = extract_json(fixed_text)
                if result:
                    return result
            except Exception:
                continue

        return {}

    async def _ask_llm_to_fix(self, broken_text: str) -> str:
        """Re-prompt LLM to fix broken JSON output."""
        # Truncate if too long (avoid token waste on retry)
        truncated = broken_text if len(broken_text) < 8000 else broken_text[:8000]
        response = await self.llm.chat.completions.create(
            model=config.long_context_model,
            max_tokens=4096,
            timeout=300.0,
            messages=[
                {"role": "system", "content": JSON_FIX_SYSTEM_PROMPT},
                {"role": "user", "content": f"以下 JSON 格式有误，请修复后重新输出：\n\n{truncated}"},
            ],
        )
        content = response.choices[0].message.content
        if not content or not content.strip():
            reasoning = getattr(response.choices[0].message, "reasoning_content", None)
            if reasoning:
                content = reasoning
        return content or ""


def extract_json(text: str) -> dict:
    """Robust JSON extraction from LLM output.

    Uses json-repair library as the primary repair tool (handles missing
    commas, trailing commas, unescaped control chars, comments, single
    quotes, and more), with a hand-rolled repair as fallback.
    """
    if not text or not text.strip():
        return {}

    text = text.strip()
    # Strip markdown code fences
    if text.startswith("```"):
        first_newline = text.find("\n")
        if first_newline != -1:
            text = text[first_newline + 1:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

    # Find outermost { ... }
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return {}

    text = text[start:end + 1]

    # Strategy A: json-repair library (handles most LLM JSON quirks)
    try:
        from json_repair import repair_json
        repaired = repair_json(text, return_objects=False)
        if repaired and repaired.strip():
            return json.loads(repaired)
    except Exception:
        pass

    # Strategy B: hand-rolled repair
    try:
        fixed = _repair_json(text)
        return json.loads(fixed)
    except json.JSONDecodeError:
        return {}


def _repair_json(text: str) -> str:
    """Fix common JSON syntax errors in LLM output."""
    # Remove // line comments (only at line start, not URL "https://")
    text = re.sub(r"(?m)^\s*//[^\n]*\n?", "", text)
    # Escape control characters inside string values
    text = _escape_control_chars_in_strings(text)
    # Remove trailing commas before } or ]
    text = re.sub(r",\s*(\}|\])", r"\1", text)
    # Fix missing colons in key-value pairs
    text = re.sub(r'(\n\s*"[^"]+")\s+("[^"]*")', r"\1: \2", text)
    # Insert missing commas at line boundaries
    text = re.sub(r'"(\s*\n\s*)"', r'",\1"', text)
    text = re.sub(r'"(\s*\n\s*)([\[{])', r'",\1\2', text)
    text = re.sub(r'(\d)(\s*\n\s*)(")', r"\1,\2\3", text)
    text = re.sub(r'([}\]])(\s*\n\s*)(")', r"\1,\2\3", text)
    text = re.sub(r'(true|false|null)(\s*\n\s*)(")', r"\1,\2\3", text)
    return text


def _escape_control_chars_in_strings(text: str) -> str:
    """Escape unescaped control chars AND bare double-quotes within JSON strings.

    Distinguishes JSON keys (where \" always terminates) from values (where
    inner \" may need escaping). Uses a state machine with lookahead.
    """
    result: list[str] = []
    in_string = False
    escape_next = False
    string_role: str = ""  # "key" or "value"

    for i, ch in enumerate(text):
        if escape_next:
            result.append(ch)
            escape_next = False
            continue
        if ch == "\\" and in_string:
            result.append(ch)
            escape_next = True
            continue
        if ch == '"':
            if not in_string:
                in_string = True
                # Determine role by looking at char before the opening quote.
                j = i - 1
                while j >= 0 and text[j] in " \t\r\n":
                    j -= 1
                string_role = "value" if (j >= 0 and text[j] == ":") else "key"
                result.append(ch)
            else:
                if string_role == "key":
                    in_string = False
                    result.append(ch)
                else:
                    m = _peek_after_whitespace(text, i + 1)
                    if m is None or m in ",:}]":
                        in_string = False
                    else:
                        result.append("\\")
                    result.append(ch)
            continue
        if in_string and ord(ch) < 0x20:
            if ch == "\n":
                result.append("\\n")
            elif ch == "\r":
                result.append("\\r")
            elif ch == "\t":
                result.append("\\t")
            else:
                result.append(f"\\u{ord(ch):04x}")
            continue
        result.append(ch)

    return "".join(result)


def _peek_after_whitespace(s: str, start: int) -> str | None:
    """Return the first non-whitespace character in s starting at start, or None."""
    for i in range(start, len(s)):
        if s[i] not in " \t\r\n":
            return s[i]
    return None
