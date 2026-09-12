---
name: geng-baike
description: 网络梗智能检索与分析。支持 9 种 LLM + 7 种搜索引擎多接口故障转移，搜索梗的定义、来源、代表视频，生成深度文化分析报告，监控每日新梗动态。
version: 2.0.0
---

# 梗百科 — 网络梗智能检索与分析

## 适用场景

当用户提出以下需求时使用本技能：
- 查询某个网络梗的含义、来源、用法
- 了解近期/今日网络热梗有哪些
- 对某个梗做深度文化分析
- 订阅每日热梗推送
- 跨平台搜索梗的代表性视频

## 核心能力

| Agent | 能力 | 触发词 |
|---|---|---|
| 梗百科 | 定义、别名、起源、时间线 | "什么是XX"、"XX是什么梗"、"XX出处" |
| 视频猎人 | B站/抖音/YouTube 代表视频 | "XX的视频"、"找XX相关视频" |
| 文化人类学家 | 深度分析报告 | "分析XX"、"XX为什么火"、"深度解读" |
| 梗情报局 | 每日热梗扫描 | "今天什么梗火"、"最近热梗"、"每日热梗" |

## 多提供商配置

本技能支持 9 种 LLM 和 7 种搜索引擎，自动故障转移。

**LLM 提供商：** OpenAI、DeepSeek、Claude、通义千问、豆包、智谱GLM、Kimi、Ollama、自定义端点
**搜索引擎：** Tavily、SerpAPI、Bing、Brave、Google CSE、百度、DuckDuckGo

设置对应环境变量的 API Key 即自动启用，无需修改代码。

## 使用方式

### CLI

```bash
python -m memeclaw.main search "梗名"     # 搜索
python -m memeclaw.main analyze "梗名"    # 深度分析
python -m memeclaw.main daily             # 每日热梗
python -m memeclaw.main info              # 查看提供商状态
python -m memeclaw.main serve             # 启动 API
```

### HTTP API

启动后访问 `http://localhost:8000/docs`，核心端点：
- `GET /search?q=梗名`
- `GET /analyze?q=梗名`
- `GET /daily-briefing`
- `GET /providers/status`（查看所有接口状态）

## 依赖

- Python 3.10+
- `pip install -r memeclaw/requirements.txt`
- MongoDB（可选，订阅和缓存功能需要）
