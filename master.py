"""Master Agent — LangGraph workflow orchestrating the full memeclaw pipeline.

State transitions:
  classify_intent → [search → parallel_search → ask_deep_analysis]
                   → [subscribe → handle_subscribe → assemble]
  ask_deep_analysis → [yes → run_anthropologist → assemble]
                     → [no  → assemble]

Every search/analysis fetches fresh data from the web — no caching.
Local file export only happens during daily push (cron / daily-briefing).
"""

import asyncio
from typing import Literal

from memeclaw.models.schemas import (
    Intent,
    MemeEncyclopediaEntry,
    WorkflowState,
)
from memeclaw.agents.encyclopedia import EncyclopediaNotFoundError


class MemeClawWorkflow:
    """LangGraph-based master workflow."""

    def __init__(self, llm_client=None, db=None):
        self.llm = llm_client
        self.db = db

        # Lazy-loaded agents
        self._encyclopedia = None
        self._video_hunter = None
        self._anthropologist = None
        self._intelligence = None

    # ── Graph Construction ──────────────────────────────────────

    def build_graph(self):
        """Build and return the compiled LangGraph workflow."""
        from langgraph.graph import StateGraph, END

        builder = StateGraph(WorkflowState)

        # Add nodes
        builder.add_node("classify_intent", self._node_classify_intent)
        builder.add_node("parallel_search", self._node_parallel_search)
        builder.add_node("handle_subscribe", self._node_handle_subscribe)
        builder.add_node("ask_deep_analysis", self._node_ask_deep_analysis)
        builder.add_node("run_anthropologist", self._node_run_anthropologist)
        builder.add_node("assemble_response", self._node_assemble_response)

        # Set entry
        builder.set_entry_point("classify_intent")

        # Conditional edges
        builder.add_conditional_edges(
            "classify_intent",
            self._route_after_intent,
            {
                "search": "parallel_search",
                "subscribe": "handle_subscribe",
                "unknown": "assemble_response",
            }
        )

        builder.add_conditional_edges(
            "parallel_search",
            self._route_after_search,
            {
                "continue": "ask_deep_analysis",
                "error": "assemble_response",
            }
        )
        builder.add_edge("handle_subscribe", "assemble_response")

        builder.add_conditional_edges(
            "ask_deep_analysis",
            self._route_after_deep_analysis_check,
            {
                "yes": "run_anthropologist",
                "no": "assemble_response",
            }
        )

        builder.add_edge("run_anthropologist", "assemble_response")
        builder.add_edge("assemble_response", END)

        return builder.compile()

    # ── Node Implementations ────────────────────────────────────

    async def _node_classify_intent(self, state: WorkflowState) -> WorkflowState:
        """Classify user input into intent + extract meme name.

        Preserves intent if already explicitly set by API caller (non-UNKNOWN).
        """
        user_input = state.user_input.strip()
        print("classify_intent: received input:", user_input)
        # Respect pre-set intent from API / upstream caller
        if state.intent != Intent.UNKNOWN:
            pass  # Keep existing intent
        elif any(kw in user_input for kw in ["订阅", "subscribe", "每日", "推送"]):
            state.intent = Intent.SUBSCRIBE
        elif any(kw in user_input for kw in ["分析", "报告", "深度", "analyze", "report"]):
            state.intent = Intent.DEEP_ANALYSIS
        elif user_input:
            state.intent = Intent.SEARCH
        else:
            state.intent = Intent.UNKNOWN
            state.error = "请输入搜索关键词，例如：'什么是「这很开门」'"

        # Extract meme name (simple heuristic: strip quotes and question words)
        state.meme_name = self._extract_meme_name(user_input)
        print(f"classify_intent: classified intent={state.intent}, meme_name='{state.meme_name}'")
        return state

    async def _node_parallel_search(self, state: WorkflowState) -> WorkflowState:
        """Execute encyclopedia + video hunter in parallel."""
        print(f"[workflow] parallel_search start: meme_name='{state.meme_name}'")
        if not state.meme_name:
            state.error = "无法识别梗名"
            print("[workflow] parallel_search: no meme_name, error set")
            return state

        enc_task = self._get_encyclopedia().research(state.meme_name)
        vid_task = self._get_video_hunter().hunt(state.meme_name)

        enc_result, vid_result = await asyncio.gather(enc_task, vid_task, return_exceptions=True)
        print(f"[workflow] parallel_search: enc_result type={type(enc_result).__name__}")

        if isinstance(enc_result, Exception):
            print(f"[workflow] parallel_search: enc_result is Exception: {type(enc_result).__name__}: {enc_result}")
            state.error = f"未找到关于「{state.meme_name}」的信息"
            suggestions = await self._get_known_meme_names()
            if state.meme_name:
                suggestions = [n for n in suggestions if n != state.meme_name]
            state.suggestions = suggestions[:5]
            return state

        if not isinstance(enc_result, MemeEncyclopediaEntry):
            print(f"[workflow] parallel_search: enc_result is not MemeEncyclopediaEntry, type={type(enc_result).__name__}")
            state.error = f"未找到关于「{state.meme_name}」的信息"
            suggestions = await self._get_known_meme_names()
            if state.meme_name:
                suggestions = [n for n in suggestions if n != state.meme_name]
            state.suggestions = suggestions[:5]
            return state

        enc_entry = enc_result
        print(f"[workflow] parallel_search: entry def='{enc_entry.definition[:60]}...' def_empty={not enc_entry.definition.strip()}")

        if not enc_entry.definition.strip():
            print("[workflow] parallel_search: empty definition, setting error")
            state.error = f"未找到关于「{state.meme_name}」的可靠信息"
            state.encyclopedia_result = None
            suggestions = await self._get_known_meme_names()
            if state.meme_name:
                suggestions = [n for n in suggestions if n != state.meme_name]
            state.suggestions = suggestions[:5]
            return state

        state.encyclopedia_result = enc_entry
        print(f"[workflow] parallel_search: SUCCESS, encyclopedia_result set")

        if isinstance(vid_result, Exception):
            pass
        else:
            state.video_result = vid_result

        return state

    async def _node_handle_subscribe(self, state: WorkflowState) -> WorkflowState:
        """Register a user for daily meme briefings."""
        if self.db:
            # In production, user_id comes from auth context
            user_id = state.user_input  # Placeholder
            await self.db.add_subscriber(user_id)
            state.final_response = "已成功订阅每日新梗简报！每天早上你会收到最新的网络热梗推送。"
            state.user_subscription_requested = True
        else:
            state.final_response = "订阅功能需要数据库支持，请先配置 MongoDB。"
        return state

    async def _node_ask_deep_analysis(self, state: WorkflowState) -> WorkflowState:
        """This node is a checkpoint — in interactive mode, pauses to ask user.

        In automated mode (non-interactive), checks a flag on the state.
        """
        # In non-interactive mode, skip if user already requested analysis
        if state.intent == Intent.DEEP_ANALYSIS:
            state.user_wants_deep_analysis = True
        return state

    async def _node_run_anthropologist(self, state: WorkflowState) -> WorkflowState:
        """Generate deep cultural analysis report."""
        if not state.meme_name:
            state.error = "无法生成报告：梗名缺失"
            return state

        enc_data = state.encyclopedia_result.model_dump() if state.encyclopedia_result else None
        try:
            report = await self._get_anthropologist().analyze(state.meme_name, enc_data)
            state.analysis_result = report
        except Exception as e:
            state.error = f"深度分析生成失败: {e}"
        return state

    async def _node_assemble_response(self, state: WorkflowState) -> WorkflowState:
        """Assemble the final integrated response card."""
        print(f"[workflow] assemble: error={repr(state.error)}, enc_result={'SET' if state.encyclopedia_result else 'None'}, final_response={'SET' if state.final_response else 'empty'}")

        if state.error and not state.encyclopedia_result:
            msg = f"### 出错了\n\n{state.error}"
            if state.suggestions:
                msg += "\n\n### 你可能想搜这些梗\n\n"
                msg += "\n".join(f"- {n}" for n in state.suggestions)
                msg += "\n\n> 输入上方的梗名试试看？"
            state.final_response = msg
            return state

        if state.final_response:
            return state  # Already set (e.g., subscribe path)

        parts = []

        # 1. Encyclopedia card
        if state.encyclopedia_result:
            parts.append(self._format_encyclopedia_card(state.encyclopedia_result))

        # 2. Video section
        if state.video_result and state.video_result.videos:
            parts.append(self._get_video_hunter().format_for_display(state.video_result))

        # 3. Analysis report
        if state.analysis_result:
            parts.append(self._get_anthropologist().format_report_markdown(state.analysis_result))

        if not parts:
            state.final_response = f"未找到关于「{state.meme_name}」的信息。"
        else:
            state.final_response = "\n\n---\n\n".join(parts)

            # Append deep analysis prompt if not yet generated
            if not state.analysis_result and not state.user_wants_deep_analysis:
                state.final_response += (
                    "\n\n---\n\n"
                    "> 需要生成**深度文化分析报告**吗？回复「分析」即可。"
                )

        print(f"[workflow] assemble: final_response length={len(state.final_response)}, preview='{state.final_response[:100]}...'")
        return state

    # ── Routing Functions ───────────────────────────────────────

    def _route_after_intent(self, state: WorkflowState) -> Literal["search", "subscribe", "unknown"]:
        if state.intent == Intent.SUBSCRIBE:
            return "subscribe"
        if state.intent in (Intent.SEARCH, Intent.DEEP_ANALYSIS):
            return "search"
        return "unknown"

    def _route_after_search(self, state: WorkflowState) -> Literal["continue", "error"]:
        if state.error and not state.encyclopedia_result:
            return "error"
        return "continue"

    def _route_after_deep_analysis_check(self, state: WorkflowState) -> Literal["yes", "no"]:
        if state.user_wants_deep_analysis:
            return "yes"
        return "no"

    # ── Helpers ─────────────────────────────────────────────────

    async def _get_known_meme_names(self) -> list[str]:
        """Return list of known meme names from the database."""
        if self.db is None:
            return []
        try:
            cursor = self.db.db["memes"].find({}, {"meme_name": 1}).sort("last_update_time", -1).limit(20)
            names = []
            async for doc in cursor:
                names.append(doc["meme_name"])
            return names
        except Exception:
            return []

    def _extract_meme_name(self, user_input: str) -> str:
        """Extract meme name from user input."""
        import re
        # Try to find content in quotes: 「xxx」 or "xxx" or 'xxx'
        match = re.search(r"[「「](.+?)[」」]", user_input)
        if match:
            return match.group(1)
        match = re.search(r'"(.+?)"', user_input)
        if match:
            return match.group(1)
        match = re.search(r"'(.+?)'", user_input)
        if match:
            return match.group(1)
        # Fallback: remove common question prefix words
        result = re.sub(r"什么是|告诉我|搜索|查找|解释.*?叫", "", user_input).strip()
        return result if result else user_input.strip()

    def _format_encyclopedia_card(self, entry: MemeEncyclopediaEntry) -> str:
        lines = [
            f"## 梗百科：{entry.meme_name}",
            "",
            f"**别名**：{'、'.join(entry.aliases) if entry.aliases else '无'}",
            "",
            f"**定义**：{entry.definition}",
        ]
        if entry.origin_platform:
            lines.append(f"\n**起源平台**：{entry.origin_platform}")
        if entry.originator:
            lines.append(f"\n**起源者**：{entry.originator}")
        if entry.origin_url:
            lines.append(f"\n**原始出处**：{entry.origin_url}")
        if entry.key_timeline:
            lines.append("\n**关键时间线**：")
            for t in entry.key_timeline:
                lines.append(f"- {t.get('date', '?')} — {t.get('event', '?')}")
        if entry.related_memes:
            lines.append(f"\n**相关梗**：{'、'.join(entry.related_memes)}")
        if entry.references:
            lines.append(f"\n**参考链接**：{len(entry.references)} 条")
        return "\n".join(lines)

    # ── Lazy Agent Accessors ────────────────────────────────────

    def _get_encyclopedia(self):
        if self._encyclopedia is None:
            from memeclaw.agents.encyclopedia import EncyclopediaAgent
            self._encyclopedia = EncyclopediaAgent(llm_client=self.llm)
        return self._encyclopedia

    def _get_video_hunter(self):
        if self._video_hunter is None:
            from memeclaw.agents.video_hunter import VideoHunterAgent
            self._video_hunter = VideoHunterAgent()
        return self._video_hunter

    def _get_anthropologist(self):
        if self._anthropologist is None:
            from memeclaw.agents.anthropologist import AnthropologistAgent
            self._anthropologist = AnthropologistAgent(llm_client=self.llm)
        return self._anthropologist

    def _get_intelligence(self):
        if self._intelligence is None:
            from memeclaw.agents.intelligence import IntelligenceAgent
            self._intelligence = IntelligenceAgent(llm_client=self.llm, db=self.db)
        return self._intelligence

    # ── Daily Cron Entry Point ──────────────────────────────────

    async def run_daily_intelligence(self, progress_callback=None):
        """Called by cron scheduler at 3 AM daily. Exports results to local files.

        Returns the IntelligenceBriefing object.
        Passes progress_callback through for streaming progress updates.
        """
        agent = self._get_intelligence()
        briefing = await agent.run_daily_scan(progress_callback=progress_callback)
        # Export to local files in a thread to avoid blocking the event loop
        # (critical for streaming responses — sync file I/O blocks all coroutines)
        await asyncio.to_thread(agent.export_briefing, briefing)
        return briefing
