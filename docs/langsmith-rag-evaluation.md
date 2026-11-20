# LangSmith RAG 量化评估实验（LLM / configured）

## 目的

使用仓库实际的 `KnowledgeService.search()` 与 `KnowledgeService.answer()`，在固定题集上评估 **在线 embedding + LLM 回答**（`configured`）。LangSmith 保存每道题的输入、检索片段、最终回答、模式、耗时、评分和调用轨迹。数据上传到 LangSmith；请仅用可公开的教学材料运行，勿上传私人笔记。

离线词法检索 / 本地 `eval.rag_benchmark` 看板仅用于开发调试，**不作为汇报产物**；仓库只保留拉取后的 LangSmith 摘要（见下文）。

## 实验设置

- 题集：`services/api/eval/gold/rag_small_sample.json`（**v3 / `rag_dsai5205_v3`**），约 **41** 题：Chapter 3–6 PDF 分章题、`search_basics.txt` 检索算法 drill、对比、跨文档、中文改写、资料外拒答。
- 语料：四份 `DSAI5205_Chapter3_2026.pdf` … `Chapter6.pdf`（用 `scripts/sync-eval-corpus.ps1` 复制到 `eval/corpus/dsai5205/`，**不入库**）+ `eval/corpus/search_basics.txt`。每题可用 `documents` 限定检索范围；默认五份全库。每次运行在临时数据库中重新导入，独立会话回答每题。
- 中英 cue：`must_answer_all_groups` 支持每组多别名（如 `crossover` / `交叉`），避免 LLM 中文答对却被英文子串打成 0 分。
- 运行模式：**`configured`**（读取项目环境变量 / 桌宠 Settings 中的 embedding 与 LLM）。题集变更后会创建新的 `doudou-rag-<hash>` 数据集。
- 检索 cue：只检查 `search()` 返回片段；答案 cue：只检查 `answer()` 的回答，**不**把来源片段中的词算作答案正确（LangSmith）。中文改写题检索失败记 0 分。
- 确定性指标：
  - `retrieval_cue_at_k`：资料内题 any/all 检索 cue 命中，且无禁止 cue；`retrieval_all` 单独报告 must_retrieve_all。
  - `retrieval_rejection`：资料外题是否没有返回片段。
  - `answer_cue` / `answer_all` / `answer_clean`：回答含 any/all 关键词，且不含禁止泄漏词。
  - `mode_ok`：实际 mode 落在 expect_mode，且不在 forbid_modes。
  - `refusal_accuracy`：资料外题是否返回 `no_evidence`。
  - `citation_presence`：对 LLM 回答检查合法 `[S#]`。
- 建议加 **`--judge`**（Windows：`-Judge`），增加四个独立的 0/1 评审模型指标：`correctness`、`groundedness`、`answer_relevance`、`retrieval_relevance`。无证据拒答题不计前三项，仍由 `refusal_accuracy` 评分。参考答案在 `eval/gold/rag_reference_answers.json`。

关键词指标是**自动代理指标**；四项语义分数是模型评审意见，不等于经人工确认的事实。评审模型若与被测模型相同，可能产生共同偏差，最好另选评审模型并抽样人工复核。它们不是真正的 Recall@k。

## 仓库内保留的结果文件

跑完实验后可用 `python -m eval.langsmith_pull_summary --project <实验项目名>` 拉取聚合分，默认写入：

- `services/api/eval/out/langsmith-configured-judge-summary.json`

仅上述 LangSmith LLM 摘要以 git 跟踪；`eval/out/` 下其它本地生成文件会被忽略。

## Windows PowerShell 一键运行

在仓库根目录（需 LangSmith API Key 与项目 `.env` 中的 LLM / embedding 配置）：

```powershell
.\run-langsmith-rag.ps1 -Judge
```

脚本会建立 `services/api/.venv`、安装依赖，并在需要时隐藏输入 LangSmith API Key。不会在磁盘写入密钥。`configured` 模式需按 `.env.example` 配置模型与密钥，勿提交 `.env`。

## 手动运行（macOS / Linux / 已有 Python 环境）

```bash
cd services/api
pip install "langsmith>=0.3,<1"
export LANGSMITH_API_KEY=...
python -m eval.langsmith_rag --mode configured --judge
```

需要 `LLM_MODEL`、`LLM_API_KEY` / `DASHSCOPE_API_KEY`、`LLM_BASE_URL`，以及语义向量时的 `EMBEDDING_*`。会产生模型与向量 API 费用。

在 LangSmith 的 **Datasets / Experiments** 打开 `doudou-rag-<hash>`，实验名类似 `doudou-configured-judge-<id>`。题集变更会创建新数据集。

## 汇报建议

先报告每一类题的题数与分数（例如拒答、对比、改写），再展示 LangSmith 或摘要 JSON 中的失败题。不要把单课程小样本结果称为泛化效果。