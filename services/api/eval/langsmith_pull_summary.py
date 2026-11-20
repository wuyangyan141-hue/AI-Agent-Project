"""Pull aggregate scores from a LangSmith experiment project name."""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from langsmith import Client

from .rag_benchmark import DEFAULT_GOLD, EVAL_DIR

DEFAULT_OUT = EVAL_DIR / 'out' / 'langsmith-configured-judge-summary.json'


def unwrap(d):
    inner = (d or {}).get('inputs')
    return inner if isinstance(inner, dict) else (d or {})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--project', required=True)
    parser.add_argument('--gold', type=Path, default=DEFAULT_GOLD)
    parser.add_argument('--out', type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    client = Client()
    runs = list(client.list_runs(project_name=args.project, is_root=True, limit=80))
    kind_map = {c['id']: c['kind'] for c in json.loads(args.gold.read_text(encoding='utf-8'))['cases']}
    keys = [
        'retrieval_cue_at_k', 'answer_cue', 'answer_all', 'answer_clean',
        'refusal_accuracy', 'correctness', 'groundedness', 'answer_relevance',
        'citation_presence', 'retrieval_relevance',
    ]
    agg: dict[str, dict] = defaultdict(lambda: {'n': 0, 's': 0.0, 'fails': []})
    by_case: dict[str, dict] = {}
    for run in runs:
        cid = unwrap(run.inputs).get('case_id', '?')
        for fb in client.list_feedback(run_ids=[str(run.id)]):
            if fb.score is None:
                continue
            k = fb.key
            agg[k]['n'] += 1
            agg[k]['s'] += float(fb.score)
            by_case.setdefault(cid, {'kind': kind_map.get(cid, '?'), 'scores': {}})
            by_case[cid]['scores'][k] = float(fb.score)
            if float(fb.score) < 1:
                agg[k]['fails'].append(cid)

    print(f'runs={len(runs)} project={args.project}')
    for k in keys:
        if agg[k]['n']:
            mean = agg[k]['s'] / agg[k]['n']
            fails = sorted(set(agg[k]['fails']))
            print(f'{k}: {mean:.1%} (n={agg[k]["n"]}) fails={len(fails)}')

    summary = {
        'experiment': args.project,
        'n': len(runs),
        'metrics': {
            k: {
                'mean': agg[k]['s'] / agg[k]['n'] if agg[k]['n'] else None,
                'n': agg[k]['n'],
                'fails': sorted(set(agg[k]['fails'])),
            }
            for k in sorted(agg)
            if agg[k]['n']
        },
        'cases': by_case,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Wrote {args.out}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())