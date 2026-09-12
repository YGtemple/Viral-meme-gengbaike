"""Web 搜索工具 — 基于多提供商抽象层，自动故障转移。

支持 7 种搜索引擎：Tavily / SerpAPI / Bing / Brave / Google / 百度 / DuckDuckGo
按优先级自动尝试，任一成功即返回。
"""

import asyncio
from typing import Any

from memeclaw.config import config
from memeclaw.search_providers import SearchProviderManager, get_default_search_manager


def _get_manager() -> SearchProviderManager:
    """获取搜索管理器（带优先级配置）。"""
    mgr = get_default_search_manager()
    # 如果配置了自定义优先级，重建
    if config.search_priority:
        from memeclaw.search_providers import reset_default_search_manager
        reset_default_search_manager()
        mgr = SearchProviderManager.from_env(priority_order=config.search_priority)
    return mgr


async def web_search(query: str, max_results: int = 10) -> list[dict[str, Any]]:
    """搜索网络内容，返回 [{title, url, snippet}]。

    自动按优先级尝试各搜索引擎，故障转移。
    如果 config.search_api 指定了具体提供商（非 "auto"），则只用该提供商。
    """
    mgr = _get_manager()
    provider = config.search_api if config.search_api != "auto" else "auto"
    results = await mgr.search(query, max_results=max_results, provider=provider)
    return [
        {"title": r.title, "url": r.url, "snippet": r.snippet}
        for r in results
    ]


# ── 平台热梗搜索查询（保留原有逻辑，底层走多提供商）──

PLATFORM_SEARCH_QUERIES = {
    "general": [
        "今天网上最火的是什么梗 出处 含义",
        "最新网络热梗 流行语 解释",
        "最近流行的梗 什么意思 怎么来的 出处",
        "互联网热梗 流行语 含义 出处",
    ],
    "douyin": [
        "抖音 今天什么梗最火 意思",
        "抖音 最近流行梗 出处 怎么火的",
        "抖音热点 新梗 网络流行语",
    ],
    "bilibili": [
        "B站 最近流行什么梗 解释",
        "bilibili 热门梗 出处 含义",
        "B站弹幕 新梗 意思 最近流行",
    ],
    "weibo": [
        "微博 今天什么梗上热搜 解释",
        "微博热搜 梗 含义 出处",
        "微博 流行语 网络热梗 最近",
    ],
    "xiaohongshu": [
        "小红书 最近流行的梗 含义 怎么来的",
        "小红书 网络热梗 流行语",
        "小红书 新梗 出处 意思 流行",
    ],
    "zhihu": [
        "知乎 最近有什么新梗 解释",
        "知乎 网络热梗 流行语 出处",
    ],
}

_SEARCH_SEMAPHORE = asyncio.Semaphore(6)
_MAX_PER_PLATFORM = 8


async def search_platform_memes() -> list[dict[str, Any]]:
    """跨平台搜索热梗，合并去重后返回。"""
    async def _search_one(query: str, platform: str) -> list[dict[str, Any]]:
        async with _SEARCH_SEMAPHORE:
            try:
                return await _search_with_source(query, platform)
            except Exception as e:
                print(f"[search] {platform} query '{query}' failed: {e}")
                return []

    tasks = []
    for platform, queries in PLATFORM_SEARCH_QUERIES.items():
        for q in queries:
            tasks.append(_search_one(q, platform))

    results = await asyncio.gather(*tasks, return_exceptions=True)

    by_platform: dict[str, list] = {}
    for r in results:
        if isinstance(r, list):
            for item in r:
                plat = item.get("source_platform", "unknown")
                by_platform.setdefault(plat, []).append(item)

    merged = []
    for plat, items in by_platform.items():
        deduped = _deduplicate_results(items)
        merged.extend(deduped[:_MAX_PER_PLATFORM])
    return merged


async def search_platform_memes_grouped() -> dict[str, list[dict[str, Any]]]:
    """跨平台搜索热梗，按平台分组返回。"""
    async def _search_one(query: str, platform: str) -> list[dict[str, Any]]:
        async with _SEARCH_SEMAPHORE:
            try:
                return await _search_with_source(query, platform)
            except Exception as e:
                print(f"[search] {platform} query '{query}' failed: {e}")
                return []

    tasks = []
    for platform, queries in PLATFORM_SEARCH_QUERIES.items():
        for q in queries:
            tasks.append(_search_one(q, platform))

    results = await asyncio.gather(*tasks, return_exceptions=True)

    grouped: dict[str, list] = {}
    for r in results:
        if isinstance(r, list):
            for item in r:
                plat = item.get("source_platform", "unknown")
                grouped.setdefault(plat, []).append(item)

    for plat in grouped:
        grouped[plat] = _deduplicate_results(grouped[plat])[:_MAX_PER_PLATFORM]
    return grouped


async def search_social_context(meme_name: str) -> list[dict[str, Any]]:
    """搜索梗的社会背景上下文。"""
    queries = [
        f"{meme_name} 梗 起源 出处",
        f"{meme_name} 流行 背景 社会事件",
        f"{meme_name} meme origin context",
    ]
    results = []
    for q in queries:
        results.extend(await web_search(q, max_results=5))
    return _deduplicate_results(results)


async def search_academic_papers(meme_name: str) -> list[dict[str, Any]]:
    """搜索相关学术论文。"""
    queries = [
        f"meme theory {meme_name} cultural transmission",
        f"模因 传播 {meme_name} 网络文化",
        "internet meme culture social psychology research",
    ]
    results = []
    for q in queries:
        results.extend(await web_search(q, max_results=5))
    return _deduplicate_results(results)


async def _search_with_source(query: str, source: str) -> list[dict[str, Any]]:
    results = await web_search(query, max_results=3)
    for r in results:
        r["query"] = query
        r["source_platform"] = source
    return results


def _deduplicate_results(results: list[dict]) -> list[dict]:
    seen = set()
    unique = []
    for r in results:
        url = r.get("url", "")
        if url and url not in seen:
            seen.add(url)
            unique.append(r)
    return unique
