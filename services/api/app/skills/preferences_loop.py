"""Learning preferences that actually drive plan / review / reminders."""
from __future__ import annotations

import re
from typing import Any

MEMORY_KINDS = ('目标', '薄弱点', '忌讳')
PREF_KEYS = ('language', 'study_time', 'daily_minutes', 'explanation_style', 'preference_summary')


def parse_daily_minutes(raw: str | None, default: int = 45) -> int:
    text = (raw or '').strip()
    match = re.search(r'(\d{1,3})', text)
    if not match:
        return default
    value = int(match.group(1))
    return max(15, min(240, value))


def parse_study_hm(raw: str | None) -> tuple[int, int] | None:
    """Return (hour, minute) from strings like 20:00 or 20:00–21:00."""
    text = (raw or '').strip()
    match = re.search(r'(\d{1,2})\s*[:：]\s*(\d{2})', text)
    if not match:
        return None
    hour, minute = int(match.group(1)), int(match.group(2))
    if 0 <= hour <= 23 and 0 <= minute <= 59:
        return hour, minute
    return None


def plan_budgets_from_daily(daily_minutes: int) -> dict[str, int]:
    """Map preferred daily minutes to light / standard / intensive totals."""
    base = max(15, min(240, int(daily_minutes or 45)))
    light = max(15, min(base, int(round(base * 0.45))))
    standard = max(light + 5, min(base, int(round(base * 0.7))))
    intensive = max(standard + 5, base)
    # Keep light < standard <= intensive and within bounds.
    light = max(15, min(120, light))
    standard = max(light + 5, min(180, standard))
    intensive = max(standard + 5, min(240, intensive))
    return {'light': light, 'standard': standard, 'intensive': intensive}


def load_user_preferences(user_id: str = 'local-user') -> dict[str, str]:
    from ..knowledge.integration import get_knowledge
    return dict(get_knowledge().preferences(user_id) or {})


def categorized_memories(user_id: str = 'local-user') -> dict[str, dict | None]:
    from ..knowledge.integration import get_knowledge
    rows = get_knowledge().memories(user_id)
    out: dict[str, dict | None] = {kind: None for kind in MEMORY_KINDS}
    for row in rows:
        key = (row.get('key') or '').strip()
        if key in out and out[key] is None:
            out[key] = row
    return out


def memory_context_blob(user_id: str = 'local-user') -> str:
    parts = []
    for kind, row in categorized_memories(user_id).items():
        if row and (row.get('content') or '').strip():
            parts.append(f"{kind}：{row['content'].strip()}")
    return '；'.join(parts)


def rebuild_preference_summary(prefs: dict[str, str], memories: dict[str, dict | None] | None = None) -> str:
    daily = parse_daily_minutes(prefs.get('daily_minutes'), 45)
    study = (prefs.get('study_time') or '').strip() or '未设置'
    style = (prefs.get('explanation_style') or '').strip() or '自然口语'
    language = (prefs.get('language') or '').strip() or '中文'
    mem = memories if memories is not None else {
        kind: {'content': ''} for kind in MEMORY_KINDS
    }
    goal = ((mem.get('目标') or {}).get('content') or '').strip() or '暂无'
    weak = ((mem.get('薄弱点') or {}).get('content') or '').strip() or '暂无'
    avoid = ((mem.get('忌讳') or {}).get('content') or '').strip() or '暂无'
    return (
        f'每天约 {daily} 分钟；学习时段 {study}；讲解「{style}」；语言 {language}。'
        f'目标：{goal}。薄弱点：{weak}。忌讳：{avoid}。'
    )


def save_preference_patch(user_id: str, patch: dict[str, str]) -> dict[str, str]:
    from ..knowledge.integration import get_knowledge
    kb = get_knowledge()
    current = dict(kb.preferences(user_id) or {})
    current.update({k: v for k, v in patch.items() if v is not None and str(v).strip()})
    # Always refresh the rolling summary so the panel stays honest.
    mem = categorized_memories(user_id)
    current['preference_summary'] = rebuild_preference_summary(current, mem)
    return kb.save_preferences(user_id, current)


def upsert_memory_kind(user_id: str, kind: str, content: str) -> dict:
    if kind not in MEMORY_KINDS:
        raise ValueError('记忆类型须为目标 / 薄弱点 / 忌讳')
    from ..knowledge.integration import get_knowledge
    row = get_knowledge().remember(user_id, kind, content.strip(), tags=[kind, 'auto'])
    # Refresh summary after memory change.
    prefs = load_user_preferences(user_id)
    save_preference_patch(user_id, {'preference_summary': rebuild_preference_summary(prefs, categorized_memories(user_id))})
    return row


def infer_from_utterance(text: str, user_id: str = 'local-user') -> dict[str, Any]:
    """
    Infer preference / memory updates from natural chat.
    Returns {prefs: {...}, memories: {kind: content}, notes: [str]} — empty if nothing found.
    """
    from ..agent.entities import normalize_utterance

    raw = normalize_utterance(text or '')
    if not raw or len(raw) < 2:
        return {'prefs': {}, 'memories': {}, 'notes': []}

    prefs: dict[str, str] = {}
    memories: dict[str, str] = {}
    notes: list[str] = []

    # daily_minutes
    minute_match = re.search(
        r'(?:每天|每日|一天)?(?:只能|可以|大概|大约|想)?(?:学|学习|复习|看书)?\s*(\d{1,3})\s*分钟'
        r'|每天\s*(\d{1,3})\s*分'
        r'|可用\s*(\d{1,3})\s*分钟',
        raw,
    )
    if minute_match:
        mins = next(int(g) for g in minute_match.groups() if g)
        if 15 <= mins <= 240:
            prefs['daily_minutes'] = str(mins)
            notes.append(f'记下每天约 {mins} 分钟')

    # study_time
    time_match = re.search(
        r'(?:晚上|早上|上午|下午|凌晨)?\s*(\d{1,2})\s*[:：点]\s*(\d{0,2})\s*(?:左右|开始|学习|复习)?'
        r'|(?:学习时段|学习时间|一般)\s*(\d{1,2})\s*[:：点]\s*(\d{0,2})',
        raw,
    )
    if time_match:
        groups = [g for g in time_match.groups() if g is not None]
        if len(groups) >= 1:
            hour = int(groups[0])
            minute = int(groups[1]) if len(groups) > 1 and groups[1] != '' else 0
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                prefs['study_time'] = f'{hour:02d}:{minute:02d}'
                notes.append(f'记下学习时段 {prefs["study_time"]}')

    # explanation_style
    if re.search(r'先讲结论|先结论|结论先行', raw):
        prefs['explanation_style'] = '先讲结论，再举例'
        notes.append('讲解改为先结论')
    elif re.search(r'多举例子|举例说明|要例子', raw):
        prefs['explanation_style'] = '多举例子，少空讲概念'
        notes.append('讲解改为多举例')
    elif re.search(r'讲详细|详细一点|再展开', raw):
        prefs['explanation_style'] = '讲详细，分步骤'
        notes.append('讲解改为详细分步')
    elif re.search(r'简洁|短一点|别太长', raw):
        prefs['explanation_style'] = '尽量简洁'
        notes.append('讲解改为简洁')

    if re.search(r'用中文|中文回答|说中文', raw):
        prefs['language'] = '中文，保留英文术语'
        notes.append('回答语言：中文')
    elif re.search(r'用英文|英文回答', raw):
        prefs['language'] = 'English'
        notes.append('回答语言：English')

    # Memory kinds
    goal_match = re.search(r'(?:我的目标是|目标是|想达到|这学期想|期末想)\s*(.+)$', raw)
    if goal_match:
        memories['目标'] = goal_match.group(1).strip(' 。.!！')[:200]
        notes.append('更新了学习目标')
    weak_match = re.search(
        r'(?:薄弱|总是搞混|老是不会|最不会|不懂|容易错)(?:的是|点是|在)?\s*(.+)$'
        r'|(.+?)(?:我总是搞混|我老不会|是薄弱点)',
        raw,
    )
    if weak_match:
        weak = next((g for g in weak_match.groups() if g), '').strip(' 。.!！')
        if weak:
            memories['薄弱点'] = weak[:200]
            notes.append('更新了薄弱点')
    avoid_match = re.search(
        r'(?:不要|别|忌讳|别用|不要用)\s*(.+)$'
        r'|我不喜欢\s*(.+)$',
        raw,
    )
    if avoid_match:
        avoid = next((g for g in avoid_match.groups() if g), '').strip(' 。.!！')
        if avoid and len(avoid) <= 80:
            memories['忌讳'] = avoid[:200]
            notes.append('更新了忌讳')

    # Explicit remember
    remember_match = re.search(r'(?:记住|记一下|帮我记)\s*[：:]?\s*(.+)$', raw)
    if remember_match and '目标' not in memories and '薄弱点' not in memories:
        content = remember_match.group(1).strip()
        if content:
            # Default bucket: 目标 if looks like aspiration else 薄弱点
            kind = '目标' if re.search(r'目标|想|希望|通过|考试', content) else '薄弱点'
            memories[kind] = content[:200]
            notes.append(f'写入{kind}')

    if not prefs and not memories:
        return {'prefs': {}, 'memories': {}, 'notes': []}

    if prefs:
        save_preference_patch(user_id, prefs)
    for kind, content in memories.items():
        upsert_memory_kind(user_id, kind, content)
    # Refresh summary once more with full state
    save_preference_patch(user_id, {})
    return {'prefs': prefs, 'memories': memories, 'notes': notes}


def style_instruction(user_id: str = 'local-user') -> str:
    prefs = load_user_preferences(user_id)
    style = (prefs.get('explanation_style') or '').strip()
    language = (prefs.get('language') or '').strip()
    avoid = ((categorized_memories(user_id).get('忌讳') or {}) or {}).get('content') or ''
    parts = []
    if style:
        parts.append(f'讲解方式：{style}')
    if language:
        parts.append(f'语言：{language}')
    if avoid:
        parts.append(f'忌讳：{avoid}')
    return '；'.join(parts)


def weak_topic_hint(user_id: str = 'local-user') -> str:
    row = categorized_memories(user_id).get('薄弱点')
    return ((row or {}).get('content') or '').strip()
