"""Multi-platform video search for meme-related content."""

import asyncio
from typing import Any

from memeclaw.config import config
from memeclaw.models.schemas import VideoSource


async def hunt_videos(meme_name: str) -> list[VideoSource]:
    """Search for the most representative videos of a meme across platforms.

    Runs searches against Bilibili, Douyin, and YouTube in parallel.
    Returns deduplicated, relevance-sorted video list.
    """
    platforms = {
        "bilibili": _search_bilibili,
        "douyin": _search_douyin,
        "youtube": _search_youtube,
    }

    tasks = []
    for platform in config.video_sources:
        if platform in platforms:
            tasks.append(platforms[platform](meme_name))

    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_videos = []
    for result in results:
        if isinstance(result, list):
            all_videos.extend(result)

    return _deduplicate_and_rank(all_videos)


async def _search_bilibili(keyword: str) -> list[VideoSource]:
    """Search Bilibili for meme videos using the open search API."""
    try:
        import aiohttp

        url = "https://api.bilibili.com/x/web-interface/search/type"
        params = {"keyword": keyword, "search_type": "video", "page": 1, "page_size": 10}
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://www.bilibili.com",
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, headers=headers) as resp:
                data = await resp.json()

        if data.get("code") != 0:
            return []

        videos = []
        for item in data.get("data", {}).get("result", []):
            videos.append(VideoSource(
                platform="bilibili",
                url=f"https://www.bilibili.com/video/{item.get('bvid', '')}",
                title=item.get("title", ""),
                thumbnail=item.get("pic", ""),
                embed_code=f'<iframe src="//player.bilibili.com/player.html?bvid={item.get("bvid","")}" />',
                view_count=item.get("play", 0),
            ))
        return videos
    except Exception:
        return []


async def _search_douyin(keyword: str) -> list[VideoSource]:
    """Search Douyin — uses web scraping approach (no public API)."""
    # Douyin has no public search API; this is a placeholder for a scraping-based approach.
    # In production, use Firecrawl / ScrapingBee as recommended in the design doc.
    try:
        from memeclaw.tools.search import web_search

        results = await web_search(f"site:douyin.com {keyword}")
        videos = []
        for r in results[:5]:
            videos.append(VideoSource(
                platform="douyin",
                url=r["url"],
                title=_clean_title(r["title"]),
                thumbnail=None,
            ))
        return videos
    except Exception:
        return []


async def _search_youtube(keyword: str) -> list[VideoSource]:
    """Search YouTube via web scraping (no API key required)."""
    try:
        from memeclaw.tools.search import web_search

        results = await web_search(f"site:youtube.com {keyword} meme")
        videos = []
        for r in results[:5]:
            videos.append(VideoSource(
                platform="youtube",
                url=r["url"],
                title=_clean_title(r["title"]),
                thumbnail=None,
            ))
        return videos
    except Exception:
        return []


def _clean_title(title: str) -> str:
    """Strip HTML tags and decode entities from search result titles."""
    import re
    if not title:
        return ""
    # Remove HTML tags
    title = re.sub(r"<[^>]+>", "", title)
    # Decode common HTML entities
    title = title.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    title = title.replace("&quot;", '"').replace("&#x27;", "'").replace("&#39;", "'")
    return title.strip()


def _deduplicate_and_rank(videos: list[VideoSource]) -> list[VideoSource]:
    """Deduplicate by URL and sort by view count descending."""
    seen = set()
    unique = []
    for v in videos:
        if v.url not in seen:
            seen.add(v.url)
            unique.append(v)
    return sorted(unique, key=lambda v: v.view_count or 0, reverse=True)
