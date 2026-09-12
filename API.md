# 梗百科 API 接口文档

> 版本：v2.0 | 基础路径：`http://localhost:8000`

启动服务：`python -m memeclaw.main serve`
交互式文档：`http://localhost:8000/docs`

---

## 目录

- [核心功能接口](#核心功能接口)
- [提供商管理接口](#提供商管理接口)
- [数据模型](#数据模型)
- [错误处理](#错误处理)

---

## 核心功能接口

### 1. 搜索梗

搜索梗的百科信息和代表性视频。

```
GET /search
```

**参数：**

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| q | string | 是 | 梗名或搜索关键词 |

**响应示例：**

```json
{
  "meme_name": "这很开门",
  "encyclopedia": {
    "meme_name": "这很开门",
    "aliases": ["开门"],
    "definition": "该梗源自鉴宝直播...",
    "origin_platform": "抖音",
    "origin_url": "https://...",
    "originator": "...",
    "key_timeline": [{"date": "2024-01", "event": "..."}],
    "related_memes": ["..."],
    "references": ["..."]
  },
  "videos": {
    "meme_name": "这很开门",
    "videos": [{"platform": "bilibili", "url": "...", "title": "..."}],
    "representative_video": null
  },
  "analysis": null,
  "error": null,
  "suggestions": []
}
```

---

### 2. 深度文化分析

生成指定梗的深度文化分析报告。

```
GET /analyze
```

**参数：**

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| q | string | 是 | 梗名 |

**响应示例：**

```json
{
  "meme_name": "这很开门",
  "summary": "200字摘要...",
  "meme_genealogy": "模因溯源分析...",
  "variation_analysis": "变异与选择分析...",
  "social_psychology": "社会心理映射...",
  "lifecycle_prediction": "explosion",
  "propagation_path": "graph TD...",
  "footnotes": ["参考文献1"],
  "generated_at": "2026-09-12T..."
}
```

**生命周期枚举：** `incubation`（孵化期）| `explosion`（爆发期）| `plateau`（平台期）| `decline`（衰退期）

---

### 3. 订阅每日推送

```
POST /subscribe
```

**请求体：**

```json
{
  "user_id": "user_123",
  "webhook_url": "https://your-webhook.com/callback",
  "email": "user@example.com"
}
```

**响应：**

```json
{"status": "ok", "message": "订阅成功"}
```

---

### 4. 每日热梗扫描

触发一次完整的每日热梗扫描：搜索各平台 → LLM 判定 → 生成简报。

```
GET /daily-briefing
```

**响应示例：**

```json
{
  "scan_date": "2026-09-12T...",
  "briefing": "## 梗情报局日报...",
  "summary": "今日共扫描 X 个候选梗，确认 Y 个...",
  "confirmed_hot_memes": [
    {
      "keyword": "梗名",
      "definition": "含义",
      "source_platforms": ["douyin"],
      "hot_score": 85,
      "is_hot": true,
      "judge_reason": "判定理由",
      "urls": ["https://..."]
    }
  ],
  "candidates": [...],
  "candidates_count": 10,
  "confirmed_count": 3
}
```

---

### 5. 流式热梗扫描

以 NDJSON 格式流式推送扫描进度。

```
GET /daily-briefing/stream
```

**响应格式：** 每行一个 JSON 对象

```json
{"type":"progress","message":"正在搜索抖音、B站...","step":"search"}
{"type":"progress","message":"获取到 50 条结果，大模型判断中...","step":"judge"}
{"type":"result","scan_date":"...","briefing":"...","confirmed_hot_memes":[...]}
```

进度类型：`search` → `search_done` → `judge` → `format` → `result`

---

### 6. 健康检查

```
GET /health
```

**响应：**

```json
{"status": "ok", "service": "memeclaw"}
```

---

## 提供商管理接口

### 7. 列出 LLM 提供商

```
GET /providers/llm
```

**响应：**

```json
{
  "providers": [
    {
      "name": "deepseek",
      "display_name": "DeepSeek",
      "model": "deepseek-chat",
      "base_url": "https://api.deepseek.com/v1",
      "priority": 0,
      "enabled": true,
      "available": true,
      "has_api_key": true,
      "api_type": "openai"
    }
  ]
}
```

---

### 8. 列出搜索提供商

```
GET /providers/search
```

**响应：**

```json
{
  "providers": [
    {
      "name": "tavily",
      "display_name": "Tavily AI 搜索",
      "priority": 10,
      "enabled": true,
      "available": true,
      "has_api_key": true
    }
  ]
}
```

---

### 9. 综合状态

一键获取所有 LLM 和搜索提供商的状态。

```
GET /providers/status
```

**响应：**

```json
{
  "llm": {
    "total": 9,
    "available": 3,
    "providers": [...]
  },
  "search": {
    "total": 7,
    "available": 2,
    "providers": [...]
  }
}
```

---

### 10. 测试单个 LLM 提供商

```
GET /providers/test/llm/{name}
```

**路径参数：** `name` — 提供商名称（deepseek / openai / qwen / doubao / zhipu / moonshot / anthropic / ollama / custom）

**响应：**

```json
{"name": "deepseek", "ok": true, "response": "OK"}
```

失败时：

```json
{"name": "deepseek", "ok": false, "error": "Connection timeout"}
```

---

### 11. 测试单个搜索提供商

```
GET /providers/test/search/{name}
```

**路径参数：** `name` — 提供商名称（tavily / serpapi / bing / brave / google / baidu / duckduckgo）

**响应：**

```json
{"name": "tavily", "ok": true, "results_count": 1}
```

---

### 12. 批量测试所有 LLM

```
GET /providers/test-all/llm
```

**响应：**

```json
{
  "results": [
    {"name": "deepseek", "ok": true, "response": "OK"},
    {"name": "openai", "ok": false, "error": "API key 未配置"}
  ]
}
```

---

### 13. 批量测试所有搜索引擎

```
GET /providers/test-all/search
```

**响应格式同上。**

---

## 数据模型

### MemeEncyclopediaEntry

| 字段 | 类型 | 说明 |
|---|---|---|
| meme_name | string | 梗的标准名称 |
| aliases | string[] | 别名列表 |
| definition | string | 定义（2-3句话） |
| origin_platform | string? | 起源平台 |
| origin_url | string? | 原始出处链接 |
| originator | string? | 起源者 |
| key_timeline | object[] | 时间线 [{date, event}] |
| related_memes | string[] | 相关梗 |
| references | string[] | 参考链接 |

### MemeCandidate

| 字段 | 类型 | 说明 |
|---|---|---|
| keyword | string | 梗名 |
| definition | string | 含义 |
| source_platforms | string[] | 出现平台 |
| hot_score | int | 热度评分 0-100 |
| is_hot | bool | 是否确认为热梗 |
| judge_reason | string | LLM 判定理由 |
| urls | string[] | 相关链接 |

### AnthropologistReport

| 字段 | 类型 | 说明 |
|---|---|---|
| meme_name | string | 梗名 |
| summary | string | 摘要 |
| meme_genealogy | string | 模因溯源 |
| variation_analysis | string | 变异分析 |
| social_psychology | string | 社会心理 |
| lifecycle_prediction | enum | 生命周期 |
| propagation_path | string? | Mermaid 传播路径 |
| footnotes | string[] | 参考文献 |
| generated_at | datetime | 生成时间 |

---

## 错误处理

所有接口在出错时返回标准 HTTP 状态码：

| 状态码 | 说明 |
|---|---|
| 200 | 成功 |
| 400 | 请求参数错误 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误（含 LLM/搜索全部失败） |

错误响应格式：

```json
{"detail": "错误描述"}
```

---

## cURL 示例

```bash
# 搜索
curl -s "http://localhost:8000/search?q=这很开门" | jq

# 深度分析
curl -s "http://localhost:8000/analyze?q=这很开门" | jq

# 每日热梗
curl -s "http://localhost:8000/daily-briefing" | jq

# 查看所有提供商状态
curl -s "http://localhost:8000/providers/status" | jq

# 测试 DeepSeek
curl -s "http://localhost:8000/providers/test/llm/deepseek" | jq

# 流式热梗扫描
curl -N "http://localhost:8000/daily-briefing/stream"
```
