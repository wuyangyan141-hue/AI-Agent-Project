# LangSmith RAG 量化评估实验

## 目的

使用仓库实际的 `KnowledgeService.search()` 与 `KnowledgeService.answer()`，比较固定题集上的检索与回答表现。LangSmith 保存每道题的输入、检索片段、最终回答、模式、耗时、评分和调用轨迹。数据上传到 LangSmith；请仅用可公开的教学材料运行，勿上传私人笔记。

## 实验设置

- 题集：`services/api/eval/gold/rag_small_sample.json`，当前 12 题（7 道资料内、1 道中文改写、4 道资料外）。
- 文档：`services/api/eval/corpus/search_basics.txt`。每次运行在临时数据库中重新导入，独立会话回答每题。
- 同一份题集分别运行 `offline`（本地词法检索 + 抽取式回答）和 `configured`（读取项目环境变量指定的 embedding 与 LLM）。两次实验会在 LangSmith 同一个数据集下显示。
- 检索 cue：只检查 `search()` 返回片段；答案 cue：只检查 `answer()` 的回答，**不**把来源片段中的词算作答案正确。中文改写题检索失败记 0 分。
- `retrieval_cue_at_k`：资料内题的预先标注关键词是否出现在 top-k 检索片段。`retrieval_rejection`：资料外题是否没有返回片段。
- `answer_cue`：资料内题回答是否包含预先标注的关键词且未报错或拒答。`refusal_accuracy`：资料外题是否返回 `no_evidence`。
- `citation_presence`：仅对 LLM 回答检查是否含有效的 `[S1]` 等引用；不判断引用能否支持论断。离线模式此项为 N/A。
- 加 `--judge`（Windows 为 `-Judge`）后增加四个独立的 0/1 评审模型指标：`correctness`（答案与人工参考答案）、`groundedness`（答案与最终引用片段）、`answer_relevance`（答案与问题）、`retrieval_relevance`（初始检索片段与问题）。无证据拒答题不计前三项中的 correctness、groundedness、answer_relevance，仍由 `refusal_accuracy` 评分。评审用 `.env` 中配置的模型，会增加模型调用和费用。参考答案在 `eval/gold/rag_reference_answers.json`。

关键词指标是**自动代理指标**；四项语义分数是模型评审意见，不等于经人工确认的事实。评审模型若与被测模型相同，可能产生共同偏差，最好另选评审模型并抽样人工复核。它们不是真正的 Recall@k。要测 Recall@k，需要逐题标注正确 chunk ID；要测幻觉/事实支持，需逐题人工核对，或加入独立的 LLM judge 并抽样人工复核。

## Windows PowerShell 一键运行

先撤销此前公开发送的密钥，重新生成一枚。克隆仓库后切换到 `eval/langsmith-rag` 分支。在仓库根目录运行：

```powershell
.\run-langsmith-rag.ps1 -Mode offline
.\run-langsmith-rag.ps1 -Mode configured -Judge
```

脚本会建立 `services/api/.venv`、安装依赖，并在需要时隐藏输入新的 LangSmith API Key。它不会把密钥写入文件；结束时会从当前 PowerShell 进程的环境变量中移除。若 PowerShell 不允许运行本地脚本，可在当前窗口临时执行 `Set-ExecutionPolicy -Scope Process Bypass`，然后重试。`configured` 模式仍需按项目根目录 `.env.example` 在项目根目录 `.env` 配置 LLM 模型和密钥，不要提交 `.env`。

## 手动运行（macOS / Linux / 已有 Python 环境）

在 `services/api` 目录安装项目依赖及 `pip install "langsmith>=0.3,<1"`。设置 `LANGSMITH_API_KEY`（以及需要时的 `LANGSMITH_PROJECT=doudou-rag-eval`）。密钥放在本机环境变量，不要提交到仓库。

```bash
cd services/api
python -m eval.langsmith_rag --mode offline
python -m eval.langsmith_rag --mode configured --judge
```

带 `--judge` 的命令会对每道题额外请求评审模型；如果暂时只想跑原有确定性指标，省略 `--judge` 或 `-Judge`。第二条命令还需要项目的 `LLM_MODEL`、`LLM_API_KEY` / `DASHSCOPE_API_KEY`、`LLM_BASE_URL`。若要测语义向量，还需 `EMBEDDING_PROVIDER=openai`、`EMBEDDING_MODEL` 和相应 API 地址及密钥。只运行 offline 不需要模型 API。模型调用和语义向量可能产生费用。

在 LangSmith 的 Datasets / Experiments 中打开 `doudou-rag-<hash>`，按上述指标对比两次实验并检查失败题。题集文件改变后会创建新数据集，以免新旧题目混用。脚本不会修改主项目数据库。

## 汇报建议

先报告每一类题的题数与分数（例如拒答 3/4），然后展示具体失败案例。不要把 12 道单文档小样本结果称为泛化效果。下一轮扩充到多份真实课程资料、中文释义、跨段归纳和干扰片段，再标注正确片段及参考答案，才适合形成更稳健的量化结论。
