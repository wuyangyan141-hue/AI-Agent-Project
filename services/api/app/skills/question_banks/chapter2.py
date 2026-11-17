"""Curated MCQs for DSAI5205 Chapter 2 (search / BFS / DFS / A* / GA).

Grounded in the lecture slides used by the report demo; prefer these over
auto-extracted keywords like "Chapter" / "Search" when the PDF is in scope.
"""
from __future__ import annotations

import hashlib
import re

CHAPTER2_FILENAME_MARKERS = (
    'chapter2',
    'chapter_2',
    'ch2',
    'dsai5205_chapter2',
    'dsai5205 chapter 2',
)

# Canonical study topics shown in warmup / history.
CHAPTER2_TOPICS = (
    'searching',
    'BFS',
    'DFS',
    'A* Search',
    'uninformed search',
    'Genetic Algorithm',
)

# Each item: topic, aliases, stem, options (correct first), criteria, lecture cue.
_ITEMS: tuple[dict, ...] = (
    {
        'topic': 'searching',
        'aliases': ('what is searching', 'searching', 'goal state', 'solution path'),
        'question': '根据 Chapter 2，searching 中的 solution 指的是什么？',
        'options': (
            '从 current state 到 goal state 的一条路径',
            '任意单个 goal state 节点本身',
            '只统计 cost 的数值，不含路径',
            '与当前状态无关的任意动作集合',
        ),
        'criteria': ('solution', 'path', 'goal state', 'current state'),
        'reference': 'Solution: a path from the current state to the goal state.',
        'cue': 'What is searching',
    },
    {
        'topic': 'searching',
        'aliases': ('goal state', 'current state', 'search conditions'),
        'question': '根据 Chapter 2 对 searching 的定义，goal state 表示什么？',
        'options': (
            '找到解时所处的状态（solution is found）',
            '搜索开始时的初始节点',
            'open 列表里尚未展开的节点',
            'heuristic 函数 h(n) 的最小值',
        ),
        'criteria': ('goal state', 'solution', 'searching'),
        'reference': 'Goal state: the step where the solution is found.',
        'cue': 'Goal state',
    },
    {
        'topic': 'BFS',
        'aliases': ('breadth-first search', 'breadth first', '广度优先'),
        'question': '关于 Breadth-First Search（BFS），讲义强调的主要缺点是什么？',
        'options': (
            '内存压力大：必须记住同一层尚未展开的节点',
            '一般找不到解，即使状态空间很小',
            '只会保存当前路径，因此极易漏解',
            '保证找到最长路径而不是最短路径',
        ),
        'criteria': ('BFS', 'memory', 'unexpanded nodes'),
        'reference': 'Breadth-first search is very demanding on memory; it must remember unexpanded nodes at a level.',
        'cue': 'Breadth-First Search',
    },
    {
        'topic': 'DFS',
        'aliases': ('depth-first search', 'depth first', '深度优先'),
        'question': '关于 Depth-First Search（DFS），讲义指出的典型问题是？',
        'options': (
            '遇到很深且无解的分支时可能浪费大量时间，且通常不保证最短路径',
            '必须记住每一层全部未展开节点，因此内存总是比 BFS 更大',
            '只要状态空间有限就一定返回最优解',
            '不能与 BFS 一样在有解时找到解',
        ),
        'criteria': ('DFS', 'shortest path', 'deep branches'),
        'reference': 'DFS may waste time in deep fruitless branches and generally does not find the shortest path.',
        'cue': 'Depth-First Search',
    },
    {
        'topic': 'BFS',
        'aliases': ('bfs vs dfs', 'breadth-first vs depth-first', 'S-B-G'),
        'question': '讲义从 S 到 G 的例子中，BFS 与 DFS 路径对比说明了什么？',
        'options': (
            'BFS 得到 S-B-G，DFS 得到 S-A-C-G，说明 DFS 通常不保证最短路径',
            '两者路径完全相同，因此最优性没有差别',
            'DFS 一定比 BFS 更短，因为只存当前路径',
            'BFS 找不到解，只有 DFS 能到达 G',
        ),
        'criteria': ('BFS', 'DFS', 'shortest path', 'S-B-G'),
        'reference': 'By breadth-first the path is S-B-G; by depth-first it is S-A-C-G.',
        'cue': 'From S to G',
    },
    {
        'topic': 'A* Search',
        'aliases': ('a* search', 'a-star', 'astar', 'f(n) = g(n)', 'heuristic search'),
        'question': '根据讲义，A* Search 使用的评价函数是哪一个？',
        'options': (
            'f(n) = g(n) + h(n)，其中 g 为到 n 的实际代价，h 为到目标的估计代价',
            'f(n) = g(n) − h(n)，只用启发项压低已走代价',
            'f(n) = h(n)，完全忽略从起点走到 n 的代价',
            'f(n) = g(n)，不使用任何启发信息',
        ),
        'criteria': ('A*', 'g(n)', 'h(n)', 'heuristic'),
        'reference': 'A* computes f(n) = g(n) + h(n): actual cost plus estimated cost to the goal.',
        'cue': 'The A* Search',
    },
    {
        'topic': 'A* Search',
        'aliases': ('heuristic', 'h(n)', 'informed search'),
        'question': '在 A* 中，h(n) 的作用是什么？',
        'options': (
            '估计从节点 n 到 goal 的最便宜路径代价，引导搜索走向有希望的状态',
            '记录从起点走到 n 已经花费的真实代价',
            '统计 open 列表长度，用来限制内存',
            '随机打乱扩展顺序以避免陷入局部最优',
        ),
        'criteria': ('h(n)', 'heuristic', 'goal'),
        'reference': 'h(n) estimates the cost of the cheapest path from n to the goal and guides search.',
        'cue': 'estimated cost',
    },
    {
        'topic': 'uninformed search',
        'aliases': ('blind search', 'uninformed', 'blind'),
        'question': '讲义中的 Uninformed（Blind）Search 指的是哪类方法？',
        'options': (
            '不使用领域启发信息、只按固定策略扩展节点的搜索（如 BFS/DFS）',
            '必须依赖可采纳启发式 h(n) 才能运行的搜索',
            '只在神经网络权重空间里做梯度下降',
            '只比较 crossover / mutation 算子的遗传搜索',
        ),
        'criteria': ('uninformed', 'blind search', 'BFS', 'DFS'),
        'reference': 'Uninformed (Blind) Search expands without domain heuristic guidance (e.g. BFS/DFS).',
        'cue': 'Uninformed (Blind) Search',
    },
    {
        'topic': 'Genetic Algorithm',
        'aliases': ('genetic algorithm', 'genetic', 'fitness function', 'uniform crossover'),
        'question': '关于 Genetic Algorithm（GA），下列哪项更符合讲义表述？',
        'options': (
            '用 fitness 评价个体，并通过选择、交叉（crossover）与变异产生新一代解',
            '与 A* 一样，每一步都必须保证 f(n)=g(n)+h(n) 最优',
            '只扩展当前路径上的节点，内存占用恒等于路径长度',
            '属于 uninformed search，完全不使用任何评价信息',
        ),
        'criteria': ('Genetic Algorithm', 'fitness', 'crossover'),
        'reference': 'GA evaluates individuals by fitness and creates offspring via selection, crossover and mutation.',
        'cue': 'Fitness',
    },
)


def looks_like_chapter2(filename: str | None) -> bool:
    name = re.sub(r'\s+', ' ', (filename or '')).strip().casefold()
    if not name:
        return False
    compact = re.sub(r'[^a-z0-9]+', '', name)
    if any(marker.replace('_', '').replace(' ', '') in compact for marker in CHAPTER2_FILENAME_MARKERS):
        return True
    return 'chapter2' in compact or ('dsai5205' in compact and 'chapter' in compact and '2' in compact)


def _norm(text: str) -> str:
    return re.sub(r'[^a-z0-9\u4e00-\u9fff*]+', '', (text or '').casefold())


def _score_topic(topic: str, item: dict) -> int:
    needle = _norm(topic)
    if not needle or len(needle) < 3:
        return 0
    labels = (item['topic'], *item.get('aliases', ()))
    best = 0
    for label in labels:
        token = _norm(label)
        if not token or len(token) < 3:
            continue
        if needle == token:
            best = max(best, 100)
        elif needle in token or token in needle:
            # Require the shorter side to be substantial to avoid "search" ⊂ "research".
            shorter = min(len(needle), len(token))
            if shorter >= 4:
                best = max(best, 80)
            elif shorter >= 3 and (needle.startswith(token) or token.startswith(needle)):
                best = max(best, 70)
    return best


def chapter2_match_item(topic: str, *, salt: str = '') -> dict | None:
    """Pick the best curated item for a topic, or None if no useful match."""
    ranked = sorted(
        ((_score_topic(topic, item), index, item) for index, item in enumerate(_ITEMS)),
        key=lambda row: (row[0], -row[1]),
        reverse=True,
    )
    if not ranked or ranked[0][0] < 70:
        return None
    top_score = ranked[0][0]
    pool = [item for score, _, item in ranked if score == top_score]
    if len(pool) == 1:
        return _materialize(pool[0], salt or topic)
    digest = hashlib.sha1(f'{salt}:{topic}'.encode()).hexdigest()
    return _materialize(pool[int(digest[:8], 16) % len(pool)], salt or topic)


def chapter2_quiz_items(limit: int = 3, *, salt: str = 'daily') -> list[dict]:
    """Diverse curated MCQs covering distinct Chapter 2 topics."""
    limit = max(1, min(limit, len(_ITEMS)))
    # Prefer one item per topic, cycling through bank in a stable salted order.
    by_topic: dict[str, list[dict]] = {}
    for item in _ITEMS:
        by_topic.setdefault(item['topic'], []).append(item)
    topics = list(by_topic.keys())
    order = sorted(topics, key=lambda name: hashlib.sha1(f'{salt}:{name}'.encode()).hexdigest())
    picked: list[dict] = []
    for topic in order:
        variants = by_topic[topic]
        choice = variants[int(hashlib.sha1(f'{salt}:pick:{topic}'.encode()).hexdigest()[:8], 16) % len(variants)]
        picked.append(_materialize(choice, f'{salt}:{topic}'))
        if len(picked) >= limit:
            break
    return picked


def _materialize(item: dict, salt: str) -> dict:
    correct, *distractors = item['options']
    pool = [correct, *distractors]
    # Stable shuffle so A is not always correct.
    ordered = sorted(pool, key=lambda text: hashlib.sha1(f'{salt}:{text}'.encode()).hexdigest())
    keys = 'ABCD'
    options = [{'key': keys[i], 'text': ordered[i]} for i in range(len(ordered))]
    correct_key = keys[ordered.index(correct)]
    return {
        'topic': item['topic'],
        'question': item['question'],
        'question_type': 'multiple_choice',
        'options': options,
        'correct_key': correct_key,
        'criteria': list(item['criteria']),
        'reference_answer': item['reference'],
        'cue': item.get('cue') or item['topic'],
        'bank': 'chapter2',
    }
