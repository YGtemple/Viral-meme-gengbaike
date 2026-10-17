<div align="right">

**[English](README.md)** · [简体中文](README.zh-CN.md)

</div>

# Viral-meme-gengbaike

A meme-retrieval agent that keeps working when a provider does not — three layers, multiple models, multiple search engines.

<sub>Python · LangGraph · FastAPI</sub>

---

## The design constraint

An agent that calls one model and one search API has one failure mode: when either is down, it stops. Providers rate-limit, time out, or return malformed JSON — the agent breaks with them.

So the pipeline is split into three layers, each with its own fallback:

```
intelligence.py       reasoning chain — decides what to search, what to conclude
llm_providers.py      model adapter  — rotates across configured models
search_providers.py   search adapter — rotates across configured engines
```

Each adapter is asked in turn until one answers. A failure becomes a rotation, not an exception.

## The part that took the longest

**Malformed JSON.**

Models asked for structured output return JSON wrapped in prose, or truncated when they hit a token cap. `json_repair.py` exists for that: it finds the outermost complete object and repairs the usual breakages — trailing commas, unquoted keys, truncated arrays.

Without it, every provider failure would surface at this layer instead, and the three-layer fallback would accomplish nothing.

## Layout

```
main.py                entry point
api.py                 FastAPI routes (14 KB)
intelligence.py        reasoning chain (26 KB)
master.py              orchestration (16 KB)
llm_providers.py       model adapters (15.7 KB)
search_providers.py    search adapters (15.1 KB)
llm_client_adapter.py  client shim
json_repair.py         repair for malformed model output (7 KB)
anthropologist.py      prompt construction (8 KB)
encyclopedia.py        reference lookups (9 KB)
search.py              search orchestration
video_search.py        video-specific search
video_hunter.py        video retrieval
database.py            persistence
schemas.py             request/response shapes
config.py              configuration
download/              asset handling
index.html             simple web front-end
```

## Running

```bash
pip install -r requirements.txt
cp env.example .env               # add your provider keys
python main.py
```

`start.sh` is the container entry point.

## Notes

Provider keys are read from the environment. `env.example` lists the variables; no keys are committed.

## License

MIT — see [LICENSE](LICENSE).
