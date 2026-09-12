"""统一多 LLM 提供商抽象层 — 支持 9 种主流接口 + 自动故障转移。

支持的提供商：
  - openai        OpenAI 官方 (GPT-4o / GPT-4o-mini / o1)
  - deepseek      DeepSeek (deepseek-chat / deepseek-reasoner)
  - anthropic     Anthropic Claude (claude-3-5-sonnet / claude-3-opus)
  - qwen          阿里通义千问 (qwen-plus / qwen-max / qwen-turbo)
  - doubao        字节豆包 (doubao-pro / doubao-lite)
  - zhipu         智谱 GLM (glm-4 / glm-4-flash)
  - moonshot      月之暗面 Kimi (moonshot-v1-8k / moonshot-v1-32k)
  - ollama        本地 Ollama (llama3 / qwen2 等)
  - custom        任意 OpenAI 兼容自定义端点

用法：
  from memeclaw.llm_providers import LLMProviderManager
  manager = LLMProviderManager.from_env()
  text = await manager.chat(messages=[...], model="auto")

故障转移：按 priority 顺序依次尝试，任一成功即返回；全部失败抛出最后一个异常。
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from typing import Any, Optional


# ── 提供商预设 ──────────────────────────────────────────────

PROVIDER_PRESETS: dict[str, dict[str, Any]] = {
    "openai": {
        "display_name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o-mini",
        "env_key": "OPENAI_API_KEY",
        "api_type": "openai",
    },
    "deepseek": {
        "display_name": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "default_model": "deepseek-chat",
        "env_key": "DEEPSEEK_API_KEY",
        "api_type": "openai",
    },
    "anthropic": {
        "display_name": "Anthropic Claude",
        "base_url": "https://api.anthropic.com",
        "default_model": "claude-3-5-sonnet-20241022",
        "env_key": "ANTHROPIC_API_KEY",
        "api_type": "anthropic",
    },
    "qwen": {
        "display_name": "通义千问",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "default_model": "qwen-plus",
        "env_key": "DASHSCOPE_API_KEY",
        "api_type": "openai",
    },
    "doubao": {
        "display_name": "豆包",
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "default_model": "doubao-pro-32k",
        "env_key": "ARK_API_KEY",
        "api_type": "openai",
    },
    "zhipu": {
        "display_name": "智谱 GLM",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "default_model": "glm-4-flash",
        "env_key": "ZHIPU_API_KEY",
        "api_type": "openai",
    },
    "moonshot": {
        "display_name": "Kimi 月之暗面",
        "base_url": "https://api.moonshot.cn/v1",
        "default_model": "moonshot-v1-8k",
        "env_key": "MOONSHOT_API_KEY",
        "api_type": "openai",
    },
    "ollama": {
        "display_name": "Ollama 本地",
        "base_url": "http://localhost:11434/v1",
        "default_model": "qwen2:7b",
        "env_key": None,  # no key needed
        "api_type": "openai",
    },
    "custom": {
        "display_name": "自定义 OpenAI 兼容",
        "base_url": "",
        "default_model": "",
        "env_key": "CUSTOM_LLM_API_KEY",
        "api_type": "openai",
    },
}


@dataclass
class ProviderConfig:
    """单个 LLM 提供商的配置。"""
    name: str                                    # 唯一标识，如 "deepseek"
    display_name: str                            # 展示名
    base_url: str
    api_key: str = ""
    model: str = ""                              # 该提供商使用的模型
    api_type: str = "openai"                     # openai | anthropic
    priority: int = 100                          # 优先级，数字越小越先尝试
    enabled: bool = True
    max_tokens: int = 4096
    timeout: float = 180.0
    extra_headers: dict[str, str] = field(default_factory=dict)

    def is_available(self) -> bool:
        """检查该提供商是否可用（有 API key 或不需要 key）。"""
        if not self.enabled:
            return False
        preset = PROVIDER_PRESETS.get(self.name, {})
        env_key = preset.get("env_key")
        if env_key is None:
            return True  # ollama 等不需要 key
        return bool(self.api_key) or bool(os.getenv(env_key))

    def get_effective_key(self) -> str:
        """获取实际使用的 API key（优先显式配置，其次环境变量）。"""
        if self.api_key:
            return self.api_key
        preset = PROVIDER_PRESETS.get(self.name, {})
        env_key = preset.get("env_key")
        if env_key:
            return os.getenv(env_key, "")
        return ""

    def get_effective_model(self) -> str:
        if self.model:
            return self.model
        return PROVIDER_PRESETS.get(self.name, {}).get("default_model", "")


class LLMProviderManager:
    """多 LLM 提供商管理器 — 统一 chat 接口 + 自动故障转移。"""

    def __init__(self, providers: list[ProviderConfig]):
        # 按 priority 排序
        self.providers = sorted(providers, key=lambda p: p.priority)
        self._clients: dict[str, Any] = {}
        self._last_used: Optional[str] = None

    # ── 工厂方法 ──

    @classmethod
    def from_env(cls, priority_order: Optional[list[str]] = None) -> "LLMProviderManager":
        """从环境变量自动构建提供商列表。

        priority_order: 提供商名称的优先级顺序，如 ["deepseek", "openai", "qwen"]
                        未列出的提供商按默认 priority=100 排在后面。
        """
        providers: list[ProviderConfig] = []
        priority_map = {name: i for i, name in enumerate(priority_order or [])}

        for name, preset in PROVIDER_PRESETS.items():
            env_key = preset.get("env_key")
            api_key = os.getenv(env_key, "") if env_key else ""

            # 自定义端点需要同时设置 base_url
            if name == "custom":
                base_url = os.getenv("CUSTOM_LLM_BASE_URL", "")
                model = os.getenv("CUSTOM_LLM_MODEL", "")
                if not base_url or not api_key:
                    continue  # 自定义未配置则跳过
            else:
                base_url = preset["base_url"]
                # 允许通过环境变量覆盖模型
                model_env = f"{name.upper()}_MODEL"
                model = os.getenv(model_env, preset["default_model"])

            cfg = ProviderConfig(
                name=name,
                display_name=preset["display_name"],
                base_url=base_url,
                api_key=api_key,
                model=model,
                api_type=preset["api_type"],
                priority=priority_map.get(name, 100),
                enabled=bool(api_key) or env_key is None,
            )
            providers.append(cfg)

        return cls(providers)

    @classmethod
    def from_config_dict(cls, config_list: list[dict]) -> "LLMProviderManager":
        """从配置字典列表构建（用于 API 动态配置）。"""
        providers = []
        for item in config_list:
            name = item.get("name", "custom")
            preset = PROVIDER_PRESETS.get(name, PROVIDER_PRESETS["custom"])
            providers.append(ProviderConfig(
                name=name,
                display_name=item.get("display_name", preset["display_name"]),
                base_url=item.get("base_url", preset["base_url"]),
                api_key=item.get("api_key", ""),
                model=item.get("model", preset["default_model"]),
                api_type=item.get("api_type", preset["api_type"]),
                priority=item.get("priority", 100),
                enabled=item.get("enabled", True),
                max_tokens=item.get("max_tokens", 4096),
                timeout=item.get("timeout", 180.0),
            ))
        return cls(providers)

    # ── 核心接口 ──

    async def chat(
        self,
        messages: list[dict],
        model: str = "auto",
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
        system_prompt: Optional[str] = None,
    ) -> str:
        """统一聊天接口 — 自动故障转移。

        Args:
            messages: 对话消息列表 [{"role": "user"/"system", "content": "..."}]
            model: "auto" 表示按优先级自动选择；也可指定提供商名如 "deepseek"
            max_tokens: 最大生成 token 数
            temperature: 采样温度
            system_prompt: 如果提供，会插入到 messages 开头

        Returns:
            生成的文本内容

        Raises:
            RuntimeError: 所有提供商都失败时抛出
        """
        if system_prompt:
            messages = [{"role": "system", "content": system_prompt}] + messages

        candidates = self._get_candidates(model)
        if not candidates:
            raise RuntimeError("没有可用的 LLM 提供商，请检查 API key 配置")

        last_error: Optional[Exception] = None
        for provider in candidates:
            try:
                text = await self._call_provider(provider, messages, max_tokens, temperature)
                self._last_used = provider.name
                return text
            except Exception as e:
                last_error = e
                print(f"[llm] 提供商 {provider.display_name} 调用失败: {e}，尝试下一个...")
                continue

        raise RuntimeError(f"所有 LLM 提供商均调用失败。最后错误: {last_error}")

    async def chat_with_provider(
        self,
        provider_name: str,
        messages: list[dict],
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
    ) -> tuple[str, str]:
        """调用指定提供商，返回 (文本, 实际使用的提供商名)。"""
        provider = self._get_provider(provider_name)
        if provider is None:
            raise ValueError(f"未找到提供商: {provider_name}")
        text = await self._call_provider(provider, messages, max_tokens, temperature)
        return text, provider.name

    # ── 提供商管理 ──

    def list_providers(self) -> list[dict]:
        """列出所有提供商及其状态。"""
        result = []
        for p in self.providers:
            result.append({
                "name": p.name,
                "display_name": p.display_name,
                "model": p.get_effective_model(),
                "base_url": p.base_url,
                "priority": p.priority,
                "enabled": p.enabled,
                "available": p.is_available(),
                "has_api_key": bool(p.get_effective_key()),
                "api_type": p.api_type,
            })
        return result

    async def test_provider(self, provider_name: str) -> dict:
        """测试指定提供商的连通性。"""
        provider = self._get_provider(provider_name)
        if provider is None:
            return {"name": provider_name, "ok": False, "error": "提供商不存在"}
        if not provider.is_available():
            return {"name": provider_name, "ok": False, "error": "API key 未配置"}
        try:
            text = await self._call_provider(
                provider,
                [{"role": "user", "content": "回复'OK'两个字"}],
                max_tokens=10,
                temperature=0.0,
            )
            return {"name": provider_name, "ok": True, "response": text[:100]}
        except Exception as e:
            return {"name": provider_name, "ok": False, "error": str(e)}

    async def test_all(self) -> list[dict]:
        """测试所有已启用提供商的连通性。"""
        tasks = [self.test_provider(p.name) for p in self.providers if p.enabled]
        return await asyncio.gather(*tasks)

    def get_last_used(self) -> Optional[str]:
        return self._last_used

    # ── 内部方法 ──

    def _get_candidates(self, model: str) -> list[ProviderConfig]:
        """获取候选提供商列表。"""
        if model and model != "auto":
            provider = self._get_provider(model)
            return [provider] if provider else []
        return [p for p in self.providers if p.is_available()]

    def _get_provider(self, name: str) -> Optional[ProviderConfig]:
        for p in self.providers:
            if p.name == name:
                return p
        return None

    def _get_client(self, provider: ProviderConfig) -> Any:
        """获取或创建提供商的客户端。"""
        if provider.name in self._clients:
            return self._clients[provider.name]

        if provider.api_type == "anthropic":
            from anthropic import AsyncAnthropic
            client = AsyncAnthropic(
                api_key=provider.get_effective_key(),
                base_url=provider.base_url,
            )
        else:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(
                api_key=provider.get_effective_key() or "sk-not-set",
                base_url=provider.base_url,
            )

        self._clients[provider.name] = client
        return client

    async def _call_provider(
        self,
        provider: ProviderConfig,
        messages: list[dict],
        max_tokens: Optional[int],
        temperature: float,
    ) -> str:
        """调用单个提供商。"""
        client = self._get_client(provider)
        model = provider.get_effective_model()
        tokens = max_tokens or provider.max_tokens

        if provider.api_type == "anthropic":
            # Anthropic API 格式不同
            system_msg = next((m["content"] for m in messages if m["role"] == "system"), "")
            user_messages = [m for m in messages if m["role"] != "system"]
            response = await client.messages.create(
                model=model,
                max_tokens=tokens,
                temperature=temperature,
                system=system_msg or None,
                messages=user_messages,
                timeout=provider.timeout,
            )
            # 提取文本
            text_parts = [block.text for block in response.content if hasattr(block, "text")]
            text = "\n".join(text_parts)
        else:
            # OpenAI 兼容格式
            response = await client.chat.completions.create(
                model=model,
                max_tokens=tokens,
                temperature=temperature,
                messages=messages,
                timeout=provider.timeout,
            )
            text = response.choices[0].message.content
            # 处理 reasoning 模型（如 deepseek-reasoner）的空 content
            if not text or not text.strip():
                reasoning = getattr(response.choices[0].message, "reasoning_content", None)
                if reasoning:
                    text = reasoning

        if not text:
            raise ValueError(f"提供商 {provider.display_name} 返回空内容")
        return text


# ── 便捷全局实例 ────────────────────────────────────────────

_default_manager: Optional[LLMProviderManager] = None


def get_default_manager() -> LLMProviderManager:
    """获取默认的全局 LLM 管理器（懒加载，从环境变量构建）。"""
    global _default_manager
    if _default_manager is None:
        _default_manager = LLMProviderManager.from_env()
    return _default_manager


def reset_default_manager() -> None:
    """重置全局管理器（配置变更后调用）。"""
    global _default_manager
    _default_manager = None
