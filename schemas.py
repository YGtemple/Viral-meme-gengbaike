"""Pydantic models for the entire memeclaw data flow."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Intent(str, Enum):
    SEARCH = "search"
    SUBSCRIBE = "subscribe"
    DEEP_ANALYSIS = "deep_analysis"
    UNKNOWN = "unknown"


class MemeLifecycle(str, Enum):
    INCUBATION = "incubation"  # 孵化期
    EXPLOSION = "explosion"  # 爆发期
    PLATEAU = "plateau"  # 平台期
    DECLINE = "decline"  # 衰退期


class VideoSource(BaseModel):
    platform: str  # bilibili, douyin, youtube
    url: str
    title: str
    thumbnail: Optional[str] = None
    embed_code: Optional[str] = None
    view_count: Optional[int] = None

class MemeEncyclopediaEntry(BaseModel):
    """Structured output from 梗百科 Agent."""
    meme_name: str
    aliases: list[str] = Field(default_factory=list)
    definition: str
    origin_platform: Optional[str] = None  # 贴吧/微博/抖音 etc.
    origin_url: Optional[str] = None
    originator: Optional[str] = None  # 第一个感染者
    key_timeline: list[dict] = Field(default_factory=list)  # [{date, event}]
    related_memes: list[str] = Field(default_factory=list)
    references: list[str] = Field(default_factory=list)


class VideoHunterResult(BaseModel):
    """Output from 视频猎人 Agent."""
    meme_name: str
    videos: list[VideoSource] = Field(default_factory=list)
    representative_video: Optional[VideoSource] = None


class AnthropologistReport(BaseModel):
    """Deep analysis report from 文化人类学家 Agent."""
    meme_name: str
    summary: str  # 摘要
    meme_genealogy: str  # 模因溯源
    variation_analysis: str  # 变异与选择
    social_psychology: str  # 社会心理映射
    lifecycle_prediction: MemeLifecycle  # 生命周期预测
    propagation_path: Optional[str] = None  # 传播路径图谱 (mermaid)
    footnotes: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.now)


class MemeCandidate(BaseModel):
    """A potential hot meme identified by search + LLM judging."""
    keyword: str  # 梗的名称
    definition: str = ""  # 梗的含义
    source_platforms: list[str] = Field(default_factory=list)  # 出现的平台
    hot_score: int = 0  # LLM 综合热度评分 0-100
    is_hot: bool = False  # LLM 判定是否为热梗
    judge_reason: str = ""  # LLM 判定理由
    urls: list[str] = Field(default_factory=list)  # 相关链接


class IntelligenceBriefing(BaseModel):
    """Daily briefing from 梗情报局 Agent."""
    scan_date: datetime = Field(default_factory=datetime.now)
    candidates: list[MemeCandidate] = Field(default_factory=list)  # LLM 筛选后的候选热梗
    confirmed_hot_memes: list[MemeCandidate] = Field(default_factory=list)  # 确认热梗
    summary: str = ""
    # ── Legacy fields for backward compatibility ──
    new_hot_memes: list[dict] = Field(default_factory=list)
    trending_mutations: list[dict] = Field(default_factory=list)


class MemeDocument(BaseModel):
    """MongoDB document schema for a meme."""
    meme_name: str
    aliases: list[str] = Field(default_factory=list)
    encyclopedia: Optional[MemeEncyclopediaEntry] = None
    videos: list[VideoSource] = Field(default_factory=list)
    analysis_report: Optional[AnthropologistReport] = None
    hot_index_history: list[dict] = Field(default_factory=list)  # [{date, score}]
    last_update_time: datetime = Field(default_factory=datetime.now)


class UserSubscription(BaseModel):
    user_id: str
    subscribed_at: datetime = Field(default_factory=datetime.now)
    webhook_url: Optional[str] = None
    email: Optional[str] = None
    topics: list[str] = Field(default_factory=list)  # subscribed meme names or "all"


class WorkflowState(BaseModel):
    """State object passed through the LangGraph workflow."""
    user_input: str = ""
    intent: Intent = Intent.UNKNOWN
    meme_name: Optional[str] = None
    encyclopedia_result: Optional[MemeEncyclopediaEntry] = None
    video_result: Optional[VideoHunterResult] = None
    analysis_result: Optional[AnthropologistReport] = None
    final_response: str = ""
    suggestions: list[str] = Field(default_factory=list)
    user_wants_deep_analysis: bool = False
    user_subscription_requested: bool = False
    error: Optional[str] = None
