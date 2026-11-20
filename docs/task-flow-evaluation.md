# 任务流评测（LangSmith LLM 版）

RAG 量化见 [langsmith-rag-evaluation.md](./langsmith-rag-evaluation.md)。本页只描述 **LLM 意图** 的 LangSmith 实验；确定性路由（`explicit_intent` / `route_request` / `resolve_turn`）仍在 `pytest tests/test_task_flow_benchmark.py` 中回归，**不提交**本地 `task-flow-results` 或 HTML 看板。

## LangSmith：`detect_intent`（LLM）

当规则层只能得到 `explicit_intent→chat` 时，由 `StudyAgent.detect_intent` 用在线模型选择 `plan` / `replan` / `review` / `quiz` / `today` / `next` / `chat` 等 `action`。

金标：`eval/gold/detect_intent_llm.json`（**v1.1**，12 题）。

```powershell
$env:DATABASE_PATH = "..\..\data\companion.db"
cd services/api
.\.venv\Scripts\python.exe -m eval.langsmith_detect_intent --judge
```

- 数据集：`doudou-detect-intent-<hash>`
- 实验：`doudou-detect-intent-judge-<id>`
- 指标：`used_llm`、`intent_match`；`--judge` 时有 `action_appropriate`

需 `LANGSMITH_API_KEY`，以及桌宠 Settings / `.env` 中的在线 LLM（与 RAG configured 相同思路）。

## 仓库内保留的结果文件

脚本结束会写入（可随实验更新后重跑）：

- `services/api/eval/out/detect-intent-langsmith-summary.json`

## 与 RAG 的分工

| 套件 | 测什么 |
| --- | --- |
| `eval.langsmith_rag --mode configured` | 资料检索与作答 |
| `eval.langsmith_detect_intent --judge` | 口语消息在「非口令」下的 LLM 意图 |

完整 WebSocket、计划 HITL、复习批改等端到端场景尚未纳入 LangSmith 金标；后续可加少量 `e2e` 用例并单独开实验前缀。