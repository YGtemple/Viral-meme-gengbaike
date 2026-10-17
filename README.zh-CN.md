<div align="right">

[English](README.md) · **[简体中文](README.zh-CN.md)**

</div>

# Viral-meme-gengbaike

一个在某家服务挂掉时还能继续干活的网络梗检索 Agent——三层结构、多个模型、多个搜索引擎。

<sub>Python · LangGraph · FastAPI</sub>

---

## 设计约束

只调一个模型和一个搜索 API 的 Agent 只有一种故障模式：一边挂了就停。服务方限流、超时、返回残缺 JSON，Agent 就跟着一起垮。

所以把链路拆成三层，每层各有各的回退：

```
intelligence.py       推理链——决定搜什么、得出什么结论
llm_providers.py      模型适配——在多个已配置模型之间轮换
search_providers.py   搜索适配——在多个已配置引擎之间轮换
```

依次向适配器提问，直到有一个给出答案。失败变成一次轮换，而不是抛异常。

## 最耗时的一块

**残缺 JSON。**

要求模型输出结构化内容时，它会把 JSON 包在散文里，或者撞到 token 上限被截断。`json_repair.py` 就是干这个的：找出最外层完整的对象，修补常见的残缺——多余逗号、未加引号的键、被截断的数组。

没有它，所有服务方故障都会在这一层暴露出来，三层回退等于白做。

## 目录

```
main.py                入口
api.py                 FastAPI 路由（14 KB）
intelligence.py        推理链（26 KB）
master.py              编排（16 KB）
llm_providers.py       模型适配（15.7 KB）
search_providers.py    搜索适配（15.1 KB）
llm_client_adapter.py  客户端垫片
json_repair.py         模型输出修复（7 KB）
anthropologist.py      提示词构造（8 KB）
encyclopedia.py        参考资料查询（9 KB）
search.py              搜索编排
video_search.py        视频专项搜索
video_hunter.py        视频检索
database.py            持久化
schemas.py             请求与响应结构
config.py              配置
download/              资源处理
index.html             简易前端
```

## 运行

```bash
pip install -r requirements.txt
cp env.example .env               # 填入你的服务方密钥
python main.py
```

`start.sh` 是容器入口。

## 说明

服务方密钥从环境变量读取。`env.example` 列出了全部变量；仓库里不含任何密钥。

## 许可证

MIT —— 见 [LICENSE](LICENSE)。
