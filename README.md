<div align="center">

# 🔍 梗百科 (geng-baike)

### 网络梗智能检索与分析系统

**支持 9 种 LLM + 7 种搜索引擎，多接口自动故障转移**

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-green.svg)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2+-orange.svg)](https://langchain-ai.github.io/langgraph/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[功能特性](#-功能特性) · [快速开始](#-快速开始) · [API 文档](#-api-接口) · [多提供商](#-多提供商支持) · [CLI](#-cli-命令)

</div>

---

## ✨ 功能特性

- **梗百科** — 搜索梗的定义、别名、起源平台、关键时间线
- **视频猎人** — 跨 B站/抖音/YouTube 寻找代表性视频
- **文化人类学家** — RAG 增强的深度文化分析报告（溯源/变异/社会心理/生命周期）
- **梗情报局** — 每日扫描抖音/B站/微博/小红书/知乎，LLM 判定新热梗
- **多 LLM 支持** — 9 种主流 LLM 接口，自动故障转移
- **多搜索引擎** — 7 种搜索引擎，免 Key 兜底
- **HTTP API** — 19 个 REST 端点，含提供商管理接口
- **流式输出** — 热梗扫描支持 NDJSON 流式进度推送

---

## 🏗️ 系统架构

```
[ 用户交互 ]  CLI / HTTP API / Web UI
      ↓
[ 主控 Workflow ]  LangGraph 编排
      ↓
[ 专项 Agent 集群 ]
├── 梗百科 Agent        搜索 + LLM 结构化提取
├── 视频猎人 Agent      多平台视频检索
├── 文化人类学家 Agent   RAG 深度分析报告
└── 梗情报局 Agent      每日热梗扫描 + LLM 判定
      ↓
[ 多提供商抽象层 ]  自动故障转移
├── LLM  (9种)  OpenAI / DeepSeek / Claude / 通义 / 豆包 / 智谱 / Kimi / Ollama / 自定义
└── 搜索 (7种)  Tavily / SerpAPI / Bing / Brave / Google / 百度 / DuckDuckGo
      ↓
[ 存储层 ]  MongoDB | 本地 Markdown / Excel
```

---

## 🚀 快速开始

### 1. 安装

```bash
git clone https://github.com/yourname/geng-baike.git
cd geng-baike
pip install -r memeclaw/requirements.txt
```

### 2. 配置 LLM（至少一个）

```bash
# 推荐 DeepSeek（性价比高）
export DEEPSEEK_API_KEY="sk-xxx"

# 或 OpenAI
export OPENAI_API_KEY="sk-xxx"

# 或通义千问
export DASHSCOPE_API_KEY="sk-xxx"

# 或豆包
export ARK_API_KEY="your-ark-key"
```

### 3. 配置搜索引擎（可选，不配置用免 Key 兜底）

```bash
export TAVILY_API_KEY="tvly-xxx"   # 推荐，AI 优化摘要
```

### 4. 运行

```bash
# 查看所有提供商状态
python -m memeclaw.main info

# 搜索梗
python -m memeclaw.main search "这很开门"

# 每日热梗扫描
python -m memeclaw.main daily

# 启动 API 服务
python -m memeclaw.main serve
# → http://localhost:8000/docs
```

---

## 🔌 多提供商支持

### LLM 提供商（9 种）

| 提供商 | 环境变量 | 默认模型 | 需 Key |
|---|---|---|---|
| OpenAI | `OPENAI_API_KEY` | gpt-4o-mini | ✅ |
| DeepSeek | `DEEPSEEK_API_KEY` | deepseek-chat | ✅ |
| Anthropic Claude | `ANTHROPIC_API_KEY` | claude-3-5-sonnet | ✅ |
| 通义千问 | `DASHSCOPE_API_KEY` | qwen-plus | ✅ |
| 豆包 | `ARK_API_KEY` | doubao-pro-32k | ✅ |
| 智谱 GLM | `ZHIPU_API_KEY` | glm-4-flash | ✅ |
| Kimi | `MOONSHOT_API_KEY` | moonshot-v1-8k | ✅ |
| Ollama 本地 | — | qwen2:7b | ❌ |
| 自定义端点 | `CUSTOM_LLM_BASE_URL` + Key + Model | — | ✅ |

**优先级配置：**
```bash
export MEMECLAW_LLM_PRIORITY="deepseek,openai,qwen,ollama"
```
排在前面的先调用，失败自动切换下一个。

### 搜索引擎（7 种）

| 提供商 | 环境变量 | 特点 | 需 Key |
|---|---|---|---|
| Tavily | `TAVILY_API_KEY` | AI 优化摘要，推荐 | ✅ |
| SerpAPI | `SERPAPI_KEY` | Google 结果 | ✅ |
| Bing | `BING_API_KEY` | 微软搜索 | ✅ |
| Brave | `BRAVE_API_KEY` | 隐私友好 | ✅ |
| Google CSE | `GOOGLE_API_KEY` + `GOOGLE_CSE_CX` | 自定义搜索 | ✅ |
| 百度 | — | 中文结果好 | ❌ |
| DuckDuckGo | — | 免 Key 兜底 | ❌ |

**优先级配置：**
```bash
export MEMECLAW_SEARCH_PRIORITY="tavily,serpapi,baidu"
```

---

## 📡 API 接口

启动服务后访问 `http://localhost:8000/docs` 查看交互式文档。

### 核心功能

| 端点 | 方法 | 说明 |
|---|---|---|
| `/search?q=梗名` | GET | 搜索梗，返回百科 + 视频 |
| `/analyze?q=梗名` | GET | 生成深度文化分析报告 |
| `/subscribe` | POST | 订阅每日新梗推送 |
| `/daily-briefing` | GET | 触发每日热梗扫描 |
| `/daily-briefing/stream` | GET | 流式热梗扫描（NDJSON） |
| `/health` | GET | 健康检查 |

### 提供商管理

| 端点 | 方法 | 说明 |
|---|---|---|
| `/providers/llm` | GET | 列出所有 LLM 提供商状态 |
| `/providers/search` | GET | 列出所有搜索提供商状态 |
| `/providers/status` | GET | 一键获取所有提供商综合状态 |
| `/providers/test/llm/{name}` | GET | 测试指定 LLM 连通性 |
| `/providers/test/search/{name}` | GET | 测试指定搜索引擎连通性 |
| `/providers/test-all/llm` | GET | 批量测试所有 LLM |
| `/providers/test-all/search` | GET | 批量测试所有搜索引擎 |

### 示例

```bash
# 搜索梗
curl "http://localhost:8000/search?q=这很开门"

# 查看 LLM 提供商状态
curl "http://localhost:8000/providers/llm"

# 测试 DeepSeek 连通性
curl "http://localhost:8000/providers/test/llm/deepseek"

# 每日热梗扫描（流式）
curl "http://localhost:8000/daily-briefing/stream"
```

---

## 💻 CLI 命令

```bash
python -m memeclaw.main search "梗名"       # 搜索梗
python -m memeclaw.main analyze "梗名"      # 深度分析
python -m memeclaw.main daily               # 每日热梗扫描
python -m memeclaw.main info                # 查看系统配置和提供商状态
python -m memeclaw.main serve               # 启动 API 服务
python -m memeclaw.main cron                # 启动定时任务
python -m memeclaw.main subscribe           # 订阅推送
```

---

## 📁 项目结构

```
geng-baike/
├── SKILL.md                          # AI 技能说明书
├── README.md                         # 本文件
├── LICENSE                           # MIT 协议
├── .gitignore
├── memeclaw/
│   ├── __init__.py
│   ├── config.py                     # 多提供商配置
│   ├── main.py                       # CLI 入口
│   ├── api.py                        # FastAPI 服务（19 端点）
│   ├── llm_providers.py              # 9种 LLM 提供商抽象层
│   ├── search_providers.py           # 7种搜索引擎抽象层
│   ├── llm_client_adapter.py         # OpenAI 兼容适配器
│   ├── agents/
│   │   ├── encyclopedia.py           # 梗百科 Agent
│   │   ├── video_hunter.py           # 视频猎人 Agent
│   │   ├── anthropologist.py         # 文化人类学家 Agent
│   │   └── intelligence.py           # 梗情报局 Agent
│   ├── workflows/
│   │   └── master.py                 # LangGraph 主控
│   ├── tools/
│   │   ├── search.py                 # 搜索工具
│   │   ├── video_search.py           # 视频搜索
│   │   └── json_repair.py            # JSON 修复
│   ├── models/
│   │   └── schemas.py                # 数据模型
│   ├── storage/
│   │   └── database.py               # MongoDB 存储
│   ├── static/
│   │   └── index.html                # Web 前端
│   └── requirements.txt              # Python 依赖
└── docs/
    └── API.md                        # 完整接口文档
```

---

## ⚙️ 环境变量完整列表

### LLM

| 变量 | 说明 |
|---|---|
| `OPENAI_API_KEY` | OpenAI Key |
| `DEEPSEEK_API_KEY` | DeepSeek Key |
| `ANTHROPIC_API_KEY` | Anthropic Key |
| `DASHSCOPE_API_KEY` | 通义千问 Key |
| `ARK_API_KEY` | 豆包 Key |
| `ZHIPU_API_KEY` | 智谱 Key |
| `MOONSHOT_API_KEY` | Kimi Key |
| `CUSTOM_LLM_BASE_URL` | 自定义端点 URL |
| `CUSTOM_LLM_API_KEY` | 自定义端点 Key |
| `CUSTOM_LLM_MODEL` | 自定义端点模型 |
| `MEMECLAW_LLM_PRIORITY` | LLM 优先级（逗号分隔） |
| `{PROVIDER}_MODEL` | 覆盖指定提供商模型（如 `DEEPSEEK_MODEL`） |

### 搜索

| 变量 | 说明 |
|---|---|
| `TAVILY_API_KEY` | Tavily Key |
| `SERPAPI_KEY` | SerpAPI Key |
| `BING_API_KEY` | Bing Key |
| `BRAVE_API_KEY` | Brave Key |
| `GOOGLE_API_KEY` | Google Key |
| `GOOGLE_CSE_CX` | Google CSE ID |
| `MEMECLAW_SEARCH_PRIORITY` | 搜索优先级 |

### 系统

| 变量 | 说明 | 默认值 |
|---|---|---|
| `MONGO_URI` | MongoDB 地址 | `mongodb://localhost:27017` |
| `MEMECLAW_EXPORT_DIR` | 报告导出目录 | `./data/reports` |

---

## 🔄 故障转移机制

```
LLM:  请求 → 优先级1 → 成功？→ 返回
                ↓ 失败
           优先级2 → 成功？→ 返回
                ↓ 失败
           ... → 全部失败 → 抛出异常

搜索: 请求 → 优先级1 → 有结果？→ 返回
                ↓ 失败/空
           优先级2 → 有结果？→ 返回
                ↓ 失败/空
           ... → 全部失败 → 返回空列表（不中断主流程）
```

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

---

## 📄 License

MIT License — 详见 [LICENSE](LICENSE)

---

<div align="center">

用 ❤️ 构建 | 基于 LangGraph + FastAPI

</div>
