"""视频猎人 Agent — finds the most representative videos for a given meme.

Searches Bilibili, Douyin, YouTube and ranks by relevance.
"""

from memeclaw.models.schemas import VideoHunterResult, VideoSource
from memeclaw.tools.video_search import hunt_videos


class VideoHunterAgent:
    """Multi-platform video search agent."""

    async def hunt(self, meme_name: str) -> VideoHunterResult:
        """Search across all configured video platforms for meme content."""
        videos = await hunt_videos(meme_name)

        representative = None
        if videos:
            # Pick the most-viewed video as representative
            representative = videos[0]

        return VideoHunterResult(
            meme_name=meme_name,
            videos=videos[:10],
            representative_video=representative,
        )

    def format_for_display(self, result: VideoHunterResult) -> str:
        """Format video results as a display-friendly Markdown card."""
        lines = [f"### 视频搜索结果：{result.meme_name}\n"]
        if result.representative_video:
            v = result.representative_video
            lines.append(f"**代表视频**: [{v.title}]({v.url}) — {v.platform}")
            if v.embed_code:
                lines.append(f"\n{v.embed_code}")
        lines.append(f"\n**更多视频** ({len(result.videos)} 个):")
        for v in result.videos[:5]:
            views = f"{v.view_count:,}" if v.view_count else "N/A"
            lines.append(f"- [{v.title}]({v.url}) [{v.platform}] — {views} 次播放")
        return "\n".join(lines)
