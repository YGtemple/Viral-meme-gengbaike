"""LLM 客户端适配器 — 将多提供商管理器包装为 OpenAI 兼容接口。

现有 Agent 代码使用 self.llm.chat.completions.create(...) 调用，
本适配器提供完全兼容的接口，底层走多提供商故障转移。
"""

from __future__ import annotations

from typing import Any, Optional

from memeclaw.llm_providers import LLMProviderManager


class _Choice:
    def __init__(self, text: str):
        self.message = _Message(text)


class _Message:
    def __init__(self, text: str):
        self.content = text
        self.reasoning_content = None


class _Response:
    def __init__(self, text: str):
        self.choices = [_Choice(text)]


class _ChatCompletions:
    def __init__(self, manager: LLMProviderManager, default_model: str = "auto"):
        self._manager = manager
        self._default_model = default_model

    async def create(
        self,
        model: Optional[str] = None,
        messages: list[dict] = None,
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
        timeout: Optional[float] = None,
        **kwargs: Any,
    ) -> _Response:
        """兼容 OpenAI chat.completions.create 接口。"""
        messages = messages or []
        use_model = model or self._default_model
        text = await self._manager.chat(
            messages=messages,
            model=use_model,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return _Response(text)


class _Chat:
    def __init__(self, manager: LLMProviderManager, default_model: str = "auto"):
        self.completions = _ChatCompletions(manager, default_model)


class LLMClientAdapter:
    """OpenAI 兼容的 LLM 客户端适配器。

    用法（与现有代码完全兼容）：
        llm = LLMClientAdapter.from_env()
        response = await llm.chat.completions.create(
            model="deepseek-chat",
            messages=[...],
            max_tokens=4096,
        )
        text = response.choices[0].message.content
    """

    def __init__(self, manager: LLMProviderManager, default_model: str = "auto"):
        self._manager = manager
        self.chat = _Chat(manager, default_model)

    @classmethod
    def from_env(cls, priority_order: Optional[list[str]] = None) -> "LLMClientAdapter":
        """从环境变量构建。"""
        manager = LLMProviderManager.from_env(priority_order=priority_order)
        return cls(manager)

    @classmethod
    def from_manager(cls, manager: LLMProviderManager) -> "LLMClientAdapter":
        """从已有管理器构建。"""
        return cls(manager)

    def get_manager(self) -> LLMProviderManager:
        """获取底层管理器（用于提供商管理 API）。"""
        return self._manager

    def list_providers(self) -> list[dict]:
        return self._manager.list_providers()

    async def test_provider(self, name: str) -> dict:
        return await self._manager.test_provider(name)

    async def test_all(self) -> list[dict]:
        return await self._manager.test_all()
