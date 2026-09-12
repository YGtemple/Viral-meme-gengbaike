"""统一多搜索提供商抽象层 — 支持 7 种搜索引擎 + 自动故障转移。

支持的搜索提供商：
  - duckduckgo   DuckDuckGo（免 API Key，默认兜底）
  - serpapi      SerpAPI（Google 结果，需 Key）
  - bing         Bing Search API（需 Key）
  - google       Google Custom Search（需 Key + CX）
  - tavily       Tavily AI Search（需 Key，AI 优化摘要）
  - brave        Brave Search API（需 Key）
  - baidu        百度搜索（免 Key，网页抓取）

用法：
  from memeclaw.search_providers import SearchProviderManager
  manager = SearchProviderManager.from_env()
  results = await manager.search("今天最火的梗", max_results=10)
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class SearchResult:
    """统一的搜索结果项。"""
    title: str
    url: str
    snippet: str = ""
    source: str = ""  # 提供商名称


@dataclass
class SearchProviderConfig:
    """单个搜索提供商配置。"""
    name: str
    display_name: str
    api_key: str = ""
    api_key_env: Optional[str] = None  # 环境变量名
    priority: int = 100
    enabled: bool = True
    extra: dict[str, str] = field(default_factory=dict)  # 额外参数（如 google_cx）

    def is_available(self) -> bool:
        if not self.enabled:
            return False
        if self.api_key_env is None:
            return True  # 不需要 key 的（duckduckgo, baidu）
        return bool(self.api_key) or bool(os.getenv(self.api_key_env))

    def get_key(self) -> str:
        if self.api_key:
            return self.api_key
        if self.api_key_env:
            return os.getenv(self.api_key_env, "")
        return ""


class SearchProviderManager:
    """多搜索提供商管理器 — 统一 search 接口 + 自动故障转移。"""

    def __init__(self, providers: list[SearchProviderConfig]):
        self.providers = sorted(providers, key=lambda p: p.priority)

    # ── 工厂方法 ──

    @classmethod
    def from_env(cls, priority_order: Optional[list[str]] = None) -> "SearchProviderManager":
        """从环境变量构建。"""
        priority_map = {name: i for i, name in enumerate(priority_order or [])}

        providers = [
            SearchProviderConfig(
                name="tavily",
                display_name="Tavily AI 搜索",
                api_key_env="TAVILY_API_KEY",
                priority=priority_map.get("tavily", 10),
            ),
            SearchProviderConfig(
                name="serpapi",
                display_name="SerpAPI (Google)",
                api_key_env="SERPAPI_KEY",
                priority=priority_map.get("serpapi", 20),
            ),
            SearchProviderConfig(
                name="bing",
                display_name="Bing 搜索",
                api_key_env="BING_API_KEY",
                priority=priority_map.get("bing", 30),
            ),
            SearchProviderConfig(
                name="brave",
                display_name="Brave 搜索",
                api_key_env="BRAVE_API_KEY",
                priority=priority_map.get("brave", 40),
            ),
            SearchProviderConfig(
                name="google",
                display_name="Google Custom Search",
                api_key_env="GOOGLE_API_KEY",
                priority=priority_map.get("google", 50),
                extra={"cx": os.getenv("GOOGLE_CSE_CX", "")},
            ),
            SearchProviderConfig(
                name="baidu",
                display_name="百度搜索",
                api_key_env=None,
                priority=priority_map.get("baidu", 80),
            ),
            SearchProviderConfig(
                name="duckduckgo",
                display_name="DuckDuckGo",
                api_key_env=None,
                priority=priority_map.get("duckduckgo", 90),
            ),
        ]
        return cls(providers)

    # ── 核心接口 ──

    async def search(
        self,
        query: str,
        max_results: int = 10,
        provider: str = "auto",
    ) -> list[SearchResult]:
        """统一搜索接口 — 自动故障转移。

        Args:
            query: 搜索关键词
            max_results: 最大结果数
            provider: "auto" 自动选择；或指定提供商名

        Returns:
            SearchResult 列表
        """
        candidates = self._get_candidates(provider)
        if not candidates:
            return []

        for p in candidates:
            try:
                results = await self._call_provider(p, query, max_results)
                if results:
                    return results
                print(f"[search] {p.display_name} 返回空结果，尝试下一个...")
            except Exception as e:
                print(f"[search] {p.display_name} 调用失败: {e}，尝试下一个...")
                continue

        return []

    async def search_multi(
        self,
        queries: list[str],
        max_results: int = 5,
        provider: str = "auto",
    ) -> list[SearchResult]:
        """并行搜索多个查询，合并去重结果。"""
        tasks = [self.search(q, max_results=max_results, provider=provider) for q in queries]
        results_list = await asyncio.gather(*tasks, return_exceptions=True)

        merged: list[SearchResult] = []
        seen_urls: set[str] = set()
        for r in results_list:
            if isinstance(r, list):
                for item in r:
                    if item.url and item.url not in seen_urls:
                        seen_urls.add(item.url)
                        merged.append(item)
        return merged

    # ── 管理接口 ──

    def list_providers(self) -> list[dict]:
        return [
            {
                "name": p.name,
                "display_name": p.display_name,
                "priority": p.priority,
                "enabled": p.enabled,
                "available": p.is_available(),
                "has_api_key": bool(p.get_key()),
            }
            for p in self.providers
        ]

    async def test_provider(self, name: str) -> dict:
        provider = self._get_provider(name)
        if provider is None:
            return {"name": name, "ok": False, "error": "提供商不存在"}
        if not provider.is_available():
            return {"name": name, "ok": False, "error": "API key 未配置"}
        try:
            results = await self._call_provider(provider, "test", max_results=1)
            return {"name": name, "ok": True, "results_count": len(results)}
        except Exception as e:
            return {"name": name, "ok": False, "error": str(e)}

    async def test_all(self) -> list[dict]:
        tasks = [self.test_provider(p.name) for p in self.providers if p.enabled]
        return await asyncio.gather(*tasks)

    # ── 内部方法 ──

    def _get_candidates(self, provider: str) -> list[SearchProviderConfig]:
        if provider and provider != "auto":
            p = self._get_provider(provider)
            return [p] if p else []
        return [p for p in self.providers if p.is_available()]

    def _get_provider(self, name: str) -> Optional[SearchProviderConfig]:
        for p in self.providers:
            if p.name == name:
                return p
        return None

    async def _call_provider(
        self,
        provider: SearchProviderConfig,
        query: str,
        max_results: int,
    ) -> list[SearchResult]:
        """调用单个搜索提供商。"""
        if provider.name == "duckduckgo":
            return await self._duckduckgo(query, max_results)
        elif provider.name == "serpapi":
            return await self._serpapi(query, max_results, provider.get_key())
        elif provider.name == "bing":
            return await self._bing(query, max_results, provider.get_key())
        elif provider.name == "google":
            return await self._google(query, max_results, provider.get_key(), provider.extra.get("cx", ""))
        elif provider.name == "tavily":
            return await self._tavily(query, max_results, provider.get_key())
        elif provider.name == "brave":
            return await self._brave(query, max_results, provider.get_key())
        elif provider.name == "baidu":
            return await self._baidu(query, max_results)
        else:
            raise ValueError(f"未知搜索提供商: {provider.name}")

    # ── 各提供商实现 ──

    async def _duckduckgo(self, query: str, max_results: int) -> list[SearchResult]:
        from ddgs import DDGS
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append(SearchResult(
                    title=r.get("title", ""),
                    url=r.get("href", ""),
                    snippet=r.get("body", ""),
                    source="duckduckgo",
                ))
        return results

    async def _serpapi(self, query: str, max_results: int, api_key: str) -> list[SearchResult]:
        import aiohttp
        params = {"q": query, "api_key": api_key, "num": max_results, "engine": "google"}
        async with aiohttp.ClientSession() as session:
            async with session.get("https://serpapi.com/search", params=params, timeout=30) as resp:
                data = await resp.json()
        return [
            SearchResult(
                title=r.get("title", ""),
                url=r.get("link", ""),
                snippet=r.get("snippet", ""),
                source="serpapi",
            )
            for r in data.get("organic_results", [])[:max_results]
        ]

    async def _bing(self, query: str, max_results: int, api_key: str) -> list[SearchResult]:
        import aiohttp
        headers = {"Ocp-Apim-Subscription-Key": api_key}
        params = {"q": query, "count": max_results, "mkt": "zh-CN"}
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://api.bing.microsoft.com/v7.0/search",
                headers=headers, params=params, timeout=30,
            ) as resp:
                data = await resp.json()
        return [
            SearchResult(
                title=r.get("name", ""),
                url=r.get("url", ""),
                snippet=r.get("snippet", ""),
                source="bing",
            )
            for r in data.get("webPages", {}).get("value", [])[:max_results]
        ]

    async def _google(self, query: str, max_results: int, api_key: str, cx: str) -> list[SearchResult]:
        import aiohttp
        params = {"q": query, "key": api_key, "cx": cx, "num": min(max_results, 10)}
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://www.googleapis.com/customsearch/v1",
                params=params, timeout=30,
            ) as resp:
                data = await resp.json()
        return [
            SearchResult(
                title=r.get("title", ""),
                url=r.get("link", ""),
                snippet=r.get("snippet", ""),
                source="google",
            )
            for r in data.get("items", [])[:max_results]
        ]

    async def _tavily(self, query: str, max_results: int, api_key: str) -> list[SearchResult]:
        import aiohttp
        payload = {
            "api_key": api_key,
            "query": query,
            "max_results": max_results,
            "search_depth": "basic",
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.tavily.com/search",
                json=payload, timeout=30,
            ) as resp:
                data = await resp.json()
        return [
            SearchResult(
                title=r.get("title", ""),
                url=r.get("url", ""),
                snippet=r.get("content", ""),
                source="tavily",
            )
            for r in data.get("results", [])[:max_results]
        ]

    async def _brave(self, query: str, max_results: int, api_key: str) -> list[SearchResult]:
        import aiohttp
        headers = {"Accept": "application/json", "X-Subscription-Token": api_key}
        params = {"q": query, "count": max_results}
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://api.search.brave.com/res/v1/web/search",
                headers=headers, params=params, timeout=30,
            ) as resp:
                data = await resp.json()
        return [
            SearchResult(
                title=r.get("title", ""),
                url=r.get("url", ""),
                snippet=r.get("description", ""),
                source="brave",
            )
            for r in data.get("web", {}).get("results", [])[:max_results]
        ]

    async def _baidu(self, query: str, max_results: int) -> list[SearchResult]:
        """百度搜索 — 通过网页抓取（免 Key）。"""
        import aiohttp
        from urllib.parse import quote
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }
        url = f"https://www.baidu.com/s?wd={quote(query)}&rn={max_results}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=15) as resp:
                    html = await resp.text()
            # 简单解析百度结果
            import re
            results = []
            # 百度结果在 <h3 class="t"><a ...>标题</a></h3> 和摘要中
            blocks = re.findall(
                r'<h3[^>]*class="t"[^>]*>.*?<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>.*?</h3>(.*?)(?=<h3|$)',
                html, re.DOTALL,
            )
            for link, title_raw, rest in blocks[:max_results]:
                title = re.sub(r"<[^>]+>", "", title_raw).strip()
                snippet_match = re.search(r'class="c-abstract[^"]*"[^>]*>(.*?)</span>', rest, re.DOTALL)
                snippet = re.sub(r"<[^>]+>", "", snippet_match.group(1)).strip() if snippet_match else ""
                if title:
                    results.append(SearchResult(
                        title=title, url=link, snippet=snippet, source="baidu",
                    ))
            return results
        except Exception:
            return []


# ── 便捷全局实例 ────────────────────────────────────────────

_default_search_manager: Optional[SearchProviderManager] = None


def get_default_search_manager() -> SearchProviderManager:
    global _default_search_manager
    if _default_search_manager is None:
        _default_search_manager = SearchProviderManager.from_env()
    return _default_search_manager


def reset_default_search_manager() -> None:
    global _default_search_manager
    _default_search_manager = None
