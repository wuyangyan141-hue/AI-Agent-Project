# RAG small-sample benchmark results

- Suite: `rag_small_sample_v1`
- Generated (UTC): 2026-11-18T03:11:16.547102+00:00
- Corpus: `corpus/search_basics.txt`
- Mode: offline extractive · embedding_provider=`local` · LLM=`False`

## Metrics

| Metric | Value |
| --- | ---: |
| Cases | 12 |
| Overall pass rate | 92% |
| Retrieval hit rate | 92% |
| Evidence support rate (in-scope / paraphrase) | 100% |
| Refusal accuracy (off-topic) | 75% |
| In-scope pass rate | 100% |
| Paraphrase pass rate | 100% |
| Off-topic pass rate | 75% |

## Per-case

| ID | Kind | Pass | Mode | Retrieval | Evidence |
| --- | --- | --- | --- | --- | --- |
| in_01_searching | in_scope | Y | `extractive` | True | True |
| in_02_bfs_memory | in_scope | Y | `extractive` | True | True |
| in_03_dfs_shortest | in_scope | Y | `extractive` | True | True |
| in_04_astar | in_scope | Y | `extractive` | True | True |
| in_05_uninformed | in_scope | Y | `extractive` | True | True |
| in_06_bfs_vs_dfs_path | in_scope | Y | `extractive` | True | True |
| in_07_genetic | in_scope | Y | `extractive` | True | True |
| para_01_bfs_zh | paraphrase | Y | `extractive` | True | True |
| off_01_mars | off_topic | Y | `no_evidence` | True | True |
| off_02_supervised | off_topic | N | `extractive` | False | False |
| off_03_macd | off_topic | Y | `no_evidence` | True | True |
| off_04_quantum | off_topic | Y | `no_evidence` | True | True |

## Failures / notes

- `off_02_supervised` (off_topic): mode=`extractive` · Known hard case: 'from this document' can trigger about-doc expansion and weak lexical hits.

## How to reproduce

```bash
cd services/api
.venv/Scripts/python -m eval.rag_benchmark --out ../../docs/rag-benchmark-results.md
```

Definitions: **retrieval hit** = gold cue appears in retrieved snippets (for off-topic: empty hit list). **Evidence support** = answer or sources contain a gold cue. **Refusal accuracy** = off-topic questions return `no_evidence`. Paraphrase items that honestly miss under lexical retrieval count as pass with note `honest_miss_under_lexical_retrieval`.
