"""文化人类学家 Agent — deep cultural analysis and academic report generation.

Uses RAG (Retrieval-Augmented Generation) to produce scholarly analysis:
1. Meme genealogy (模因溯源)
2. Variation & selection analysis (变异与选择)
3. Social psychology mapping (社会心理映射)
4. Lifecycle prediction (生命周期预测)
"""

from memeclaw.config import config
from memeclaw.models.schemas import AnthropologistReport, MemeLifecycle
from memeclaw.tools.search import search_academic_papers, search_social_context
from memeclaw.tools.json_repair import extract_json


ANTHROPOLOGIST_SYSTEM_PROMPT = """你是一位网络文化人类学教授，专门研究互联网迷因（Internet Meme）的传播机制和社会心理成因。

你的分析框架基于理查德·道金斯的模因学（Memetics）理论，并结合当代网络传播学研究成果。

请对给定梗进行深度分析，输出以下 JSON 结构：

{
  "summary": "200字以内的摘要，概括该梗的文化意义",
  "meme_genealogy": "模因溯源：谁第一个使用？在什么语境下诞生？最初的传播路径是什么？（300-500字）",
  "variation_analysis": "变异与选择：梗产生了哪些二次创作和变体？为什么某些变体成功传播而其他消亡？（300-500字）",
  "social_psychology": "社会心理映射：该梗反映了年轻群体的什么集体情绪？（300-500字）",
  "lifecycle_prediction": "incubation / explosion / plateau / decline 之一，只输出单词",
  "propagation_path": "用Mermaid flowchart语法描述传播路径（可选，没有则填null）",
  "footnotes": ["参考文献1", "参考文献2"]
}

## JSON 语法规则（必须严格遵守）：
- 字符串值内部的双引号必须转义为 \\"，例如 "他说\\"你好\\""
- 字符串值内部不得有未转义的换行，多行文本用 \\n 表示
- 每个字段之间必须有逗号分隔
- 只输出 JSON，不要附带任何解释文字
"""


def _parse_lifecycle(raw: str) -> str:
    """Normalise raw LLM output to a valid MemeLifecycle enum value."""
    text = raw.lower().strip()
    # Direct match
    if text in ("incubation", "explosion", "plateau", "decline"):
        return text
    # Chinese labels
    if "孵化" in text:
        return "incubation"
    if "爆发" in text or "爆火" in text:
        return "explosion"
    if "平台" in text or "稳定" in text:
        return "plateau"
    if "衰退" in text or "过气" in text:
        return "decline"
    if "增长" in text or "上升" in text or "扩散" in text:
        return "explosion"
    if "初期" in text or "萌芽" in text or "刚" in text:
        return "incubation"
    # Default: treat unknown as explosion (most common for new hot memes)
    return "explosion"


class AnthropologistAgent:
    """Generates deep cultural analysis reports using RAG-enhanced LLM."""

    def __init__(self, llm_client=None):
        self.llm = llm_client  # Should be a long-context model

    async def analyze(
        self,
        meme_name: str,
        encyclopedia_data: dict | None = None,
    ) -> AnthropologistReport:
        """Run full RAG pipeline and generate academic report."""
        # Phase 1: Retrieval — gather social context + academic references
        social_bg = await search_social_context(meme_name)
        academic_refs = await search_academic_papers(meme_name)

        # Phase 2: Augment — combine all context
        context = self._build_context(meme_name, encyclopedia_data, social_bg, academic_refs)

        # Phase 3: Generate — long-form LLM call
        raw_json = await self._generate_report(meme_name, context)
        return self._parse_report(meme_name, raw_json)

    def _parse_report(self, meme_name: str, raw: dict) -> AnthropologistReport:
        """Robust parsing: normalise lifecycle_prediction to enum, fill missing fields."""
        raw["meme_name"] = meme_name

        # Normalise lifecycle_prediction — LLM may return Chinese labels or long text
        lifecycle = str(raw.get("lifecycle_prediction", "")).strip()
        raw["lifecycle_prediction"] = _parse_lifecycle(lifecycle)

        # Ensure required fields are present
        for field in ("summary", "meme_genealogy", "variation_analysis", "social_psychology"):
            if field not in raw:
                raw[field] = "（未生成）"
        if "footnotes" not in raw:
            raw["footnotes"] = []
        if "propagation_path" not in raw:
            raw["propagation_path"] = None

        return AnthropologistReport(**raw)

    def _build_context(
        self,
        meme_name: str,
        encyclopedia_data: dict | None,
        social_bg: list[dict],
        academic_refs: list[dict],
    ) -> str:
        sections = [f"# 研究课题：梗「{meme_name}」的深度文化分析\n"]

        if encyclopedia_data:
            sections.append("## 已知梗基本信息")
            sections.append(f"- 定义：{encyclopedia_data.get('definition', 'N/A')}")
            sections.append(f"- 起源平台：{encyclopedia_data.get('origin_platform', 'N/A')}")
            sections.append(f"- 起源者：{encyclopedia_data.get('originator', 'N/A')}")
            timeline = encyclopedia_data.get("key_timeline", [])
            if timeline:
                sections.append("- 关键时间线：")
                for t in timeline:
                    sections.append(f"  - {t.get('date', '?')}: {t.get('event', '?')}")

        sections.append("\n## 社会背景资料")
        for i, r in enumerate(social_bg[:10], 1):
            sections.append(f"[{i}] {r['title']}: {r.get('snippet', '')}")

        sections.append("\n## 学术参考文献")
        for i, r in enumerate(academic_refs[:10], 1):
            sections.append(f"[{i}] {r['title']}: {r.get('snippet', '')}")

        return "\n".join(sections)

    async def _generate_report(self, meme_name: str, context: str) -> dict:
        """Call long-context LLM to generate the report via OpenAI-compatible API."""
        if self.llm is None:
            return self._mock_report(meme_name, context)

        response = await self.llm.chat.completions.create(
            model=config.long_context_model,
            max_tokens=8192,
            timeout=180.0,
            messages=[
                {"role": "system", "content": ANTHROPOLOGIST_SYSTEM_PROMPT},
                {"role": "user", "content": f"研究课题：梗「{meme_name}」\n\n{context}"},
            ],
        )
        text = response.choices[0].message.content
        if not text or not text.strip():
            raise ValueError("LLM returned empty response")
        data = extract_json(text)
        if not data:
            raise ValueError(f"Failed to parse LLM JSON output: {text[:200]}")
        return data

    def _mock_report(self, meme_name: str, context: str) -> dict:
        """Fallback template when no LLM client is available."""
        return {
            "summary": f"「{meme_name}」是一个值得深入研究的网络文化现象。",
            "meme_genealogy": "（需要 LLM 生成完整溯源分析）",
            "variation_analysis": "（需要 LLM 生成变体分析）",
            "social_psychology": "（需要 LLM 生成社会心理分析）",
            "lifecycle_prediction": "explosion",
            "propagation_path": None,
            "footnotes": [],
        }

    def format_report_markdown(self, report: AnthropologistReport) -> str:
        """Render the report as a well-formatted Markdown document."""
        lifecycle_labels = {
            MemeLifecycle.INCUBATION: "孵化期",
            MemeLifecycle.EXPLOSION: "爆发期",
            MemeLifecycle.PLATEAU: "平台期",
            MemeLifecycle.DECLINE: "衰退期",
        }
        return f"""# 深度文化分析报告：{report.meme_name}

## 摘要
{report.summary}

## 模因溯源
{report.meme_genealogy}

## 变异与选择分析
{report.variation_analysis}

## 社会心理映射
{report.social_psychology}

## 生命周期预测
**{lifecycle_labels.get(report.lifecycle_prediction, report.lifecycle_prediction)}**

{report.propagation_path or ""}

{f"## 参考文献\n" + chr(10).join(f"- {f}" for f in report.footnotes) if report.footnotes else ""}

---
*报告生成时间：{report.generated_at.strftime("%Y-%m-%d %H:%M")}*
"""
