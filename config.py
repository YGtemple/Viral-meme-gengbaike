"""MemeClaw 配置 — 支持多 LLM / 多搜索提供商 + 故障转移。

环境变量配置（按优先级自动检测，任一可用即可）：

═══ LLM 提供商（设置对应 API Key 即自动启用）═══
  OPENAI_API_KEY       OpenAI GPT-4o / o1
  DEEPSEEK_API_KEY     DeepSeek deepseek-chat
  ANTHROPIC_API_KEY    Anthropic Claude
  DASHSCOPE_API_KEY    阿里通义千问 qwen-plus
  ARK_API_KEY          字节豆包 doubao-pro
  ZHIPU_API_KEY        智谱 GLM-4
  MOONSHOT_API_KEY     Kimi moonshot-v1
  (Ollama 无需 Key，本地运行即自动检测)
  CUSTOM_LLM_BASE_URL + CUSTOM_LLM_API_KEY + CUSTOM_LLM_MODEL  自定义 OpenAI 兼容端点

═══ 搜索提供商（设置对应 API Key 即自动启用，未设置则用免 Key 的兜底）═══
  TAVILY_API_KEY       Tavily AI 搜索（推荐，摘要质量高）
  SERPAPI_KEY          SerpAPI (Google 结果)
  BING_API_KEY         Bing Search
  BRAVE_API_KEY        Brave Search
  GOOGLE_API_KEY + GOOGLE_CSE_CX  Google Custom Search
  (DuckDuckGo / 百度 免 Key，自动兜底)

═══ 优先级配置（可选）═══
  MEMECLAW_LLM_PRIORITY     逗号分隔，如 "deepseek,openai,qwen"
  MEMECLAW_SEARCH_PRIORITY  逗号分隔，如 "tavily,serpapi,bing"
"""

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Config:
    # ── LLM 多提供商 ──
    # 兼容旧配置（单提供商）
    llm_api_key: str = os.getenv("OPENAI_API_KEY", "sk-xxx")
    llm_base_url: str = os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com")
    llm_model: str = os.getenv("MEMECLAW_LLM_MODEL", "deepseek-v4-pro")
    llm_max_tokens: int = 4096
    long_context_model: str = os.getenv("MEMECLAW_LONG_CTX_MODEL", "deepseek-v4-pro")
    long_context_max_tokens: int = 3200

    # 新增：多提供商优先级
    llm_priority: list[str] = field(default_factory=lambda: _parse_priority("MEMECLAW_LLM_PRIORITY"))
    search_priority: list[str] = field(default_factory=lambda: _parse_priority("MEMECLAW_SEARCH_PRIORITY"))

    # 热梗判定专用模型（可选，不设则用默认）
    meme_judge_model: Optional[str] = os.getenv("MEMECLAW_JUDGE_MODEL")

    # ── 搜索 ──
    search_api: str = os.getenv("SEARCH_API", "auto")  # auto | duckduckgo | serpapi | ...
    serpapi_key: Optional[str] = os.getenv("SERPAPI_KEY")

    # ── 视频平台 ──
    video_sources: list = field(default_factory=lambda: ["bilibili", "douyin", "youtube"])

    # ── 存储 ──
    mongo_uri: str = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    db_name: str = "memeclaw"
    vector_db_path: str = os.getenv("VECTOR_DB_PATH", "./data/vector_store")

    # ── 情报局 ──
    cron_scan_hour: int = 0
    hot_threshold_ratio: float = 2.0
    hot_score_threshold: int = 60
    max_search_results: int = 8

    # ── 输出 ──
    export_dir: str = os.getenv("MEMECLAW_EXPORT_DIR", "./data/reports")


def _parse_priority(env_var: str) -> list[str]:
    """从环境变量解析逗号分隔的优先级列表。"""
    raw = os.getenv(env_var, "")
    if not raw:
        return []
    return [p.strip() for p in raw.split(",") if p.strip()]


config = Config()
