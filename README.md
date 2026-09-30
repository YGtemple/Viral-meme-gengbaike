# Viral-meme-gengbaike ·「梗百科 / MemeClaw」网络梗智能检索与分析系统

> 一句话简介：LangGraph+FastAPI 网络梗 Agent，多 LLM 多搜索故障转移

## 一、项目概述与定位

这是一个**网络梗（meme）智能检索与分析系统**，代号 MemeClaw，对外名"梗百科"。它把"查一个梗是什么、为什么火、代表视频、今天又出了什么新梗"这几件事做成一套多 Agent 工作流，支持 9 种 LLM 与 7 种搜索引擎，接口故障自动转移。同时也是一个带 frontmatter 的 **AI Skill（geng-baike v2.0.0）**，可被 Agent 加载触发。

四大核心能力对应四个专项 Agent：

| Agent | 能力 | 触发词 |
|---|---|---|
| 梗百科 | 梗的定义、别名、起源平台、关键时间线（搜索+LLM 结构化提取） | "XX 是什么梗""XX 出处" |
| 视频猎人 | 跨 B站/抖音/YouTube 找代表性视频 | "找 XX 相关视频" |
| 文化人类学家 | RAG 增强的深度文化分析报告（溯源/变异/社会心理/生命周期） | "分析 XX""XX 为什么火" |
| 梗情报局 | 每日扫描抖音/B站/微博/小红书/知乎，LLM 判定新热梗 | "今天什么梗火""每日热梗" |

## 二、技术架构

```
CLI / HTTP API / Web UI
        ↓
   LangGraph 主控 Workflow（master.py）
        ↓
   专项 Agent 集群（encyclopedia / video_hunter / anthropologist / intelligence）
        ↓
   多提供商抽象层（自动故障转移）
   ├─ LLM 9 种：OpenAI / DeepSeek / Claude / 通义 / 豆包 / 智谱 / Kimi / Ollama / 自定义
   └─ 搜索 7 种：Tavily / SerpAPI / Bing / Brave / Google CSE / 百度 / DuckDuckGo
        ↓
   存储：MongoDB（可选）| 本地 Markdown / Excel 导出
```

- **技术栈**：Python 3.10+、FastAPI（19 个 REST 端点）、LangGraph（Agent 编排）、Uvicorn、APScheduler（定时扫描）、MongoDB（订阅/缓存，可选）、pymongo。
- **故障转移**：LLM 按优先级依次调用，失败切下一家，全失败抛异常；搜索引擎失败/空结果则切下一家，全失败返回空列表不中断主流程。优先级用环境变量 `MEMECLAW_LLM_PRIORITY` / `MEMECLAW_SEARCH_PRIORITY` 配置。
- **流式输出**：热梗扫描支持 NDJSON 流式进度推送。

## 三、运行与使用

```bash
pip install -r memeclaw/requirements.txt     # README 中的依赖路径
export DEEPSEEK_API_KEY="sk-xxx"             # 至少配一个 LLM Key
bash start.sh                                 # 一键检查依赖/加载.env/启动 API
python3 -m memeclaw.main info                 # 查看提供商状态
python3 -m memeclaw.main search "这很开门"     # 搜索梗
python3 -m memeclaw.main analyze "这很开门"   # 深度文化分析
python3 -m memeclaw.main daily                # 每日热梗扫描
python3 -m memeclaw.main serve                # 启动 API → http://localhost:8000/docs
python3 -m memeclaw.main cron                # 启动每日定时扫描
```

核心 API 端点：`GET /search`、`GET /analyze`、`GET /daily-briefing`（含 `/stream` 流式）、`POST /subscribe`、`/health`，以及一组提供商管理端点（`/providers/llm`、`/providers/search`、`/providers/test/...`、`/providers/test-all/...`）。

## 四、目录结构（实际扁平布局）

> 注意：README 中的 `memeclaw/` 分层树是理想结构，**仓库实际把源码文件平铺在根目录**。

| 文件 | 大小 | 作用 |
|---|---|---|
| `SKILL.md` | 2KB | Skill 说明书（frontmatter：name/description/version 2.0.0，四 Agent 触发词表） |
| `README.md` | 9.9KB | 项目完整说明（特性/架构/多提供商/API/CLI/环境变量） |
| `API.md` | 7.6KB | 完整接口文档 |
| `main.py` | 6.6KB | CLI 入口（argparse：search/analyze/subscribe/daily/serve/cron/info），构建 LangGraph workflow |
| `master.py` | 16KB | LangGraph 主控工作流（build_graph、run_daily_intelligence） |
| `intelligence.py` | 26KB | **梗情报局 Agent**（最大模块）：多平台热梗扫描+LLM 判定+简报格式化 |
| `api.py` | 14KB | FastAPI 应用（19 端点，含 SSE/NDJSON 流式与提供商管理） |
| `llm_providers.py` | 15.7KB | 9 种 LLM 提供商抽象层 |
| `search_providers.py` | 15KB | 7 种搜索引擎抽象层 |
| `anthropologist.py` | 8.4KB | 文化人类学家 Agent（RAG 深度分析报告） |
| `encyclopedia.py` | 9.4KB | 梗百科 Agent（搜索+结构化提取） |
| `index.html` | 33.8KB | Web 前端单页 UI |
| `schemas.py` | 4.4KB | 数据模型（WorkflowState、Intent 等） |
| `config.py` | 3.2KB | 多提供商 dataclass 配置（优先级/模型/阈值/Mongo/导出目录） |
| `search.py` / `video_search.py` | 6KB / 4.4KB | 搜索与视频搜索工具 |
| `video_hunter.py` | 1.6KB | 视频猎人 Agent |
| `json_repair.py` | 7.2KB | LLM 输出 JSON 修复工具 |
| `llm_client_adapter.py` | 3KB | OpenAI 兼容 LLM 适配器（from_env 按优先级初始化） |
| `database.py` | 2.5KB | MongoDB 存储层 |
| `env.example` | 1.4KB | 环境变量模板（Key 均为占位） |
| `start.sh` | 0.9KB | 一键启动脚本（检查 Python/依赖/加载.env/起服务） |
| `download` | 446B | 小型辅助脚本（无扩展名） |
| `__init__.py` 及 `__init__ (1)~(5).py` | 179B / 0B×5 | 包初始化文件，括号编号者为重复空文件 |
| `LICENSE` | 1.1KB | MIT 协议 |

## 五、关键机制解读

- **`master.py`（主控）**：用 `WorkflowState` 作为 LangGraph 共享状态，按 `Intent`（如 `DEEP_ANALYSIS`、`SUBSCRIBE`）路由到不同 Agent；`main.py` 中 `search`/`analyze` 分别构造对应 state 后 `graph.ainvoke`。
- **`intelligence.py`（梗情报局）**：项目最复杂模块，负责跨平台热词抓取 → LLM 判断是否为新梗 → 按热梗评分阈值（默认 60）与 `hot_threshold_ratio` 筛选 → 生成可读简报；`cron` 命令用 APScheduler 每日定点跑。
- **`config.py`**：环境变量驱动，`config.llm_priority` / `search_priority` 解析逗号分隔优先级；`hot_score_threshold=60`、`max_search_results=8`、`cron_scan_hour=0` 为默认判定阈值。MongoDB 不可用时主流程降级运行（`main.py` 中 `db=None`）。
- **故障转移设计**：LLM 与搜索都走 `from_env(priority_order=...)` 的 Manager，`info` 命令会打印每个提供商"✅可用/❌未配置"状态。

## 六、数据/资源构成

源码全部为文本（Python/Markdown/HTML/Shell/License），**无图片、音视频、字体、压缩包等二进制文件**。`index.html` 为前端页面；运行时数据存 MongoDB 或导出到 `./data/reports`（Markdown/Excel/JSON/ICS）。仓库中无真实 API Key（均为 `sk-xxx` 占位，`env.example` 已注释）。

## 七、项目特点

1. **多提供商容错是一等公民**：9+7 种接口、自动故障转移、免 Key 兜底（DuckDuckGo/百度/Ollama），适合 Key 不稳定或想零成本跑通的场景。
2. **Agent 化 + Skill 化双形态**：既是可独立运行的 FastAPI 服务，也是带 frontmatter 的可触发 Skill。
3. **从"查梗"到"造梗洞察"**：不止检索定义，还有 RAG 文化分析与每日新梗监控，偏"梗情报/内容选题"用途。
4. **工程化**：JSON 修复、流式输出、定时任务、提供商健康检查与批量测试端点一应俱全。
