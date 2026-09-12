"""梗百科 Agent — retrieves meme definition, origin, aliases, and timeline.

Uses web search + structured LLM extraction to produce a MemeEncyclopediaEntry.
Raises EncyclopediaNotFoundError only when absolutely no information is available.
"""

from memeclaw.models.schemas import MemeEncyclopediaEntry
from memeclaw.tools.search import search_social_context, web_search
from memeclaw.tools.json_repair import extract_json


class EncyclopediaNotFoundError(Exception):
    """Raised when no search results are found for a meme."""
    pass


def _normalize_entry(raw: dict, search_snippets: str = "") -> MemeEncyclopediaEntry:
    """Normalize LLM output into a valid MemeEncyclopediaEntry.

    Handles common LLM mistakes: null/string for list fields,
    missing fields, wrong types, etc.
    """
    # Ensure lists are lists
    for field in ("aliases", "key_timeline", "related_memes", "references"):
        val = raw.get(field)
        if val is None or not isinstance(val, list):
            raw[field] = []
        else:
            raw[field] = [item for item in val if item is not None]

    # Ensure definition is a non-empty string — use search context as fallback
    if not raw.get("definition") or not isinstance(raw.get("definition"), str):
        raw["definition"] = _fallback_definition(raw.get("meme_name", "未知"), search_snippets)

    # Ensure meme_name is present
    if not raw.get("meme_name"):
        raw["meme_name"] = "未知"

    # Clean optional string fields
    for field in ("origin_platform", "origin_url", "originator"):
        if field in raw and raw[field] is not None and not isinstance(raw[field], str):
            raw[field] = str(raw[field])

    try:
        return MemeEncyclopediaEntry(**raw)
    except Exception:
        return MemeEncyclopediaEntry(
            meme_name=raw.get("meme_name", "未知"),
            definition=raw.get("definition", _fallback_definition(raw.get("meme_name", "未知"), search_snippets)),
        )


def _fallback_definition(meme_name: str, search_snippets: str = "") -> str:
    """Construct a rough definition from search snippets when LLM is unavailable."""
    if search_snippets:
        # Extract the longest snippet as a rough definition
        snippets = [s.strip() for s in search_snippets.split("\n") if len(s.strip()) > 20]
        if snippets:
            longest = max(snippets, key=len)[:200]
            return f"（基于搜索结果推断）{longest}..."
    return f"「{meme_name}」是一个网络流行梗，暂未获取到详细定义。请尝试更换关键词重新搜索。"


ENCYCLOPEDIA_SYSTEM_PROMPT = """你是一个网络迷因（Meme）百科专家，专门研究和记录中文互联网梗的起源与演变。

你的任务是基于提供的搜索资料，为指定梗生成一份结构化的百科条目。请严格按以下字段输出 JSON：

{
  "meme_name": "梗的标准名称",
  "aliases": ["别名1", "别名2"],
  "definition": "梗的简要定义（2-3句话，说清是什么意思、怎么用）",
  "origin_platform": "最早出现的平台（贴吧/微博/抖音/NGA/B站等）",
  "origin_url": "原始出处的链接（如果有）",
  "originator": "第一个创造/使用这个梗的人或账号（如果可考）",
  "key_timeline": [
    {"date": "2024-01-15", "event": "梗首次出现在XX贴吧"}
  ],
  "related_memes": ["相关梗1", "相关梗2"],
  "references": ["参考链接1", "参考链接2"]
}

要求：
- 每个字段都必须填写，没有信息的填 null 或空数组
- 时间线按时间升序排列
- 只输出 JSON，不要附带任何解释文字
"""


class EncyclopediaAgent:
    """Retrieves structured encyclopedia data for a given meme."""

    def __init__(self, llm_client=None):
        self.llm = llm_client  # OpenAI-compatible AsyncOpenAI client

    async def research(self, meme_name: str) -> MemeEncyclopediaEntry:
        """Main entry point: search + structure → MemeEncyclopediaEntry.

        Uses a cascade strategy: tries specific queries first, then broader
        fallback queries if nothing is found.
        """
        import asyncio as _asyncio

        # ── Strategy 1: targeted meme queries ──
        all_sources = []
        stage1_tasks = [
            search_social_context(meme_name),
            web_search(f"{meme_name} 梗 什么意思 出处"),
            web_search(f"{meme_name} 梗"),
        ]
        stage1_results = await _asyncio.gather(*stage1_tasks, return_exceptions=True)
        for r in stage1_results:
            if isinstance(r, list):
                all_sources.extend(r)

        valid_sources = [s for s in all_sources if s.get("url") and s.get("title") not in ("Search unavailable",)]

        # ── Strategy 2: broader queries (only if stage 1 found nothing) ──
        if not valid_sources:
            print(f"[encyclopedia] Stage 1 found no results for '{meme_name}', trying broader queries...")
            stage2_tasks = [
                web_search(f"{meme_name} 网络用语 流行语"),
                web_search(f"{meme_name} 是什么意思"),
                web_search(f"{meme_name} 出处 来源"),
                web_search(meme_name, max_results=8),  # bare name as last resort
            ]
            stage2_results = await _asyncio.gather(*stage2_tasks, return_exceptions=True)
            for r in stage2_results:
                if isinstance(r, list):
                    all_sources.extend(r)

        # Final filter
        valid_sources = [s for s in all_sources if s.get("url") and s.get("title") not in ("Search unavailable",)]
        print(f"[encyclopedia] Total sources for '{meme_name}': {len(valid_sources)} valid out of {len(all_sources)} raw")

        # Build snippet text for fallback use
        snippet_text = "\n".join(
            f"{s.get('title', '')}: {s.get('snippet', '')}"
            for s in valid_sources[:10]
        )

        if not valid_sources:
            raise EncyclopediaNotFoundError(f"未找到关于「{meme_name}」的任何信息")

        source_text = self._format_sources(valid_sources)

        # Phase 2: LLM extraction into structured format
        raw_json = await self._llm_extract(meme_name, source_text)
        return _normalize_entry(raw_json, snippet_text)

    def _format_sources(self, sources: list[dict]) -> str:
        lines = []
        for i, s in enumerate(sources[:15], 1):
            lines.append(f"[{i}] 标题: {s['title']}\n    摘要: {s.get('snippet', '')}\n    链接: {s.get('url', '')}")
        return "\n\n".join(lines)

    async def _llm_extract(self, meme_name: str, source_text: str) -> dict:
        """Call LLM to extract structured data via OpenAI-compatible API.

        Uses robust JSON extraction with multiple repair strategies —
        never crashes on malformed LLM output.
        """
        if self.llm is None:
            print("[encyclopedia] No LLM client available, using mock extraction")
            return self._mock_extraction(meme_name, source_text)

        from memeclaw.config import config
        print(f"[encyclopedia] Calling LLM model={config.llm_model} for meme='{meme_name}'")

        try:
            response = await self.llm.chat.completions.create(
                model=config.llm_model,
                max_tokens=config.llm_max_tokens,
                timeout=180.0,
                messages=[
                    {"role": "system", "content": ENCYCLOPEDIA_SYSTEM_PROMPT},
                    {"role": "user", "content": f"梗名：{meme_name}\n\n搜索资料：\n{source_text}"},
                ],
            )
        except Exception as e:
            print(f"[encyclopedia] LLM call failed: {type(e).__name__}: {e}")
            return self._mock_extraction(meme_name, source_text)

        text = response.choices[0].message.content
        print(f"[encyclopedia] LLM response received, length={len(text) if text else 0}")

        if not text or not text.strip():
            reasoning = getattr(response.choices[0].message, "reasoning_content", None)
            if reasoning:
                print(f"[encyclopedia] Using reasoning_content fallback, length={len(reasoning)}")
                text = reasoning
            else:
                print("[encyclopedia] LLM returned empty content, falling back to mock")
                return self._mock_extraction(meme_name, source_text)

        data = extract_json(text)
        if not data:
            print(f"[encyclopedia] JSON extraction FAILED, first 300 chars: {text[:300]}")
            return self._mock_extraction(meme_name, source_text)

        print(f"[encyclopedia] JSON extraction OK, keys={list(data.keys())}, def_len={len(data.get('definition', '') or '')}")
        return data

    def _mock_extraction(self, meme_name: str, source_text: str) -> dict:
        """Fallback when LLM is unavailable — builds entry from search snippets."""
        refs = [line for line in source_text.split("\n") if "http" in line]
        return {
            "meme_name": meme_name,
            "aliases": [],
            "definition": _fallback_definition(meme_name, source_text),
            "origin_platform": None,
            "origin_url": None,
            "originator": None,
            "key_timeline": [],
            "related_memes": [],
            "references": refs,
        }
