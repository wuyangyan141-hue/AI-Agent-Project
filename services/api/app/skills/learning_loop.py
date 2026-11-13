"""Coach the next step in the study loop without requiring a model key."""
from __future__ import annotations

import json
import re
from datetime import date, timedelta


def learning_status(session_id=None) -> dict:
    from ..database import store

    try:
        from .review_session import repair_vague_waiting_reviews

        repair_vague_waiting_reviews()
    except Exception:
        pass

    with store.connect() as db:
        docs_ready = False
        try:
            from ..knowledge.integration import get_knowledge
            docs_ready = any(
                item['status'] == 'ready' and not item['needs_reindex']
                for item in get_knowledge().list_documents('local-user')
            )
        except Exception:
            docs_ready = False
        tasks = store.list_tasks(db)
        open_tasks = [task for task in tasks if not task['done']]
        focus = store.focus_status(db) or {'id': None, 'remaining_seconds': 0}
        reviews = db.execute(
            "SELECT id, topic, question, status, snapshot_json FROM review_sessions WHERE session_id IS ? ORDER BY id LIMIT 8",(session_id,)
        ).fetchall()
        waiting_review = next((dict(row) for row in reviews if row['status'] == 'waiting'), None)
        if waiting_review:
            try:
                snap = json.loads(waiting_review.get('snapshot_json') or '{}')
            except Exception:
                snap = {}
            if isinstance(snap, dict):
                waiting_review['stem'] = snap.get('stem') or waiting_review.get('question')
                waiting_review['question_type'] = snap.get('question_type')
                waiting_review['options'] = snap.get('options') or []
        streak = ensure_streak(db)
    return {
        'has_documents': docs_ready,
        'open_tasks': len(open_tasks),
        'next_task': open_tasks[0] if open_tasks else None,
        'focus': focus,
        'waiting_review': waiting_review,
        'recent_reviews': [dict(row) for row in reviews],
        'streak': streak,
    }


ACHIEVEMENT_LABELS = {
    'first_focus': '第一次专注',
    'focus_60': '累计专注 60 分钟',
    'streak_3': '连续学习 3 天',
    'first_task': '完成第一个任务',
    'tasks_5': '完成 5 个任务',
    'bones_50': '攒到 50 根骨头',
    'fed_pet': '第一次喂豆豆',
    'fed_pet_5': '喂豆豆 5 次',
}

# Spend bones to feed the desk pet for a short cheer.
FEED_PET_COST = 3
PET_CHEERS = (
    '汪！这根骨头真香，你今天也超棒～',
    '嚼嚼…谢谢你！我们再学一小口好不好？',
    '收到骨头啦！豆豆给你加油：慢慢来，也算进步。',
    '嘿嘿，好吃！你完成任务的样子最帅了。',
    '骨头入库！要不要开个短专注，我陪着你？',
)


def ensure_streak(db) -> dict:
    db.execute('''
        CREATE TABLE IF NOT EXISTS study_streak (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            current_streak INTEGER NOT NULL DEFAULT 0,
            last_study_date TEXT,
            total_focus_minutes INTEGER NOT NULL DEFAULT 0,
            achievements_json TEXT NOT NULL DEFAULT '[]'
        )
    ''')
    columns = {row['name'] for row in db.execute('PRAGMA table_info(study_streak)')}
    if 'bones' not in columns:
        db.execute('ALTER TABLE study_streak ADD COLUMN bones INTEGER NOT NULL DEFAULT 0')
    if 'tasks_completed' not in columns:
        db.execute('ALTER TABLE study_streak ADD COLUMN tasks_completed INTEGER NOT NULL DEFAULT 0')
    if 'bones_spent' not in columns:
        db.execute('ALTER TABLE study_streak ADD COLUMN bones_spent INTEGER NOT NULL DEFAULT 0')
    if 'pet_feeds' not in columns:
        db.execute('ALTER TABLE study_streak ADD COLUMN pet_feeds INTEGER NOT NULL DEFAULT 0')
    row = db.execute('SELECT * FROM study_streak WHERE id=1').fetchone()
    if row is None:
        db.execute(
            'INSERT INTO study_streak(id, current_streak, total_focus_minutes, bones, tasks_completed, bones_spent, pet_feeds) '
            'VALUES (1, 0, 0, 0, 0, 0, 0)'
        )
        db.commit()
        row = db.execute('SELECT * FROM study_streak WHERE id=1').fetchone()
    data = dict(row)
    try:
        data['achievements'] = json.loads(data.get('achievements_json') or '[]')
    except Exception:
        data['achievements'] = []
    data['bones'] = int(data.get('bones') or 0)
    data['tasks_completed'] = int(data.get('tasks_completed') or 0)
    data['bones_spent'] = int(data.get('bones_spent') or 0)
    data['pet_feeds'] = int(data.get('pet_feeds') or 0)
    data['feed_cost'] = FEED_PET_COST
    data['achievement_labels'] = [ACHIEVEMENT_LABELS.get(a, a) for a in data['achievements']]
    return data


def _append_achievements(achievements: list[str], checks: list[tuple[str, bool]]) -> list[str]:
    unlocked = []
    for badge, ok in checks:
        if ok and badge not in achievements:
            achievements.append(badge)
            unlocked.append(badge)
    return unlocked


def mark_study_activity(minutes: int = 0) -> dict:
    today = date.today().isoformat()
    from ..database import store

    with store.connect() as db:
        streak = ensure_streak(db)
        last = streak.get('last_study_date')
        current = int(streak.get('current_streak') or 0)
        if last != today:
            yesterday = (date.today() - timedelta(days=1)).isoformat()
            current = current + 1 if last == yesterday else 1
        total = int(streak.get('total_focus_minutes') or 0) + max(0, minutes)
        achievements = list(streak.get('achievements') or [])
        _append_achievements(achievements, [
            ('first_focus', total >= 1),
            ('focus_60', total >= 60),
            ('streak_3', current >= 3),
        ])
        db.execute(
            'UPDATE study_streak SET current_streak=?, last_study_date=?, total_focus_minutes=?, achievements_json=? WHERE id=1',
            (current, today, total, json.dumps(achievements, ensure_ascii=False)),
        )
        db.commit()
        return ensure_streak(db)


def award_task_completion(db, minutes: int = 30, title: str = '') -> dict:
    """Grant bones when a study task is newly marked done. Caller owns the connection."""
    import random

    streak = ensure_streak(db)
    # Roughly 1 bone per 15 minutes, minimum 1.
    earned = max(1, int(round(max(5, minutes) / 15)))
    bones = int(streak.get('bones') or 0) + earned
    completed = int(streak.get('tasks_completed') or 0) + 1
    achievements = list(streak.get('achievements') or [])
    unlocked = _append_achievements(achievements, [
        ('first_task', completed >= 1),
        ('tasks_5', completed >= 5),
        ('bones_50', bones >= 50),
    ])
    today = date.today().isoformat()
    last = streak.get('last_study_date')
    current = int(streak.get('current_streak') or 0)
    if last != today:
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        current = current + 1 if last == yesterday else 1
    db.execute(
        'UPDATE study_streak SET bones=?, tasks_completed=?, achievements_json=?, '
        'current_streak=?, last_study_date=? WHERE id=1',
        (bones, completed, json.dumps(achievements, ensure_ascii=False), current, today),
    )
    db.commit()
    labels = [ACHIEVEMENT_LABELS.get(a, a) for a in unlocked]
    short = (title or '这项任务').strip()[:18]
    cheers = (
        f'汪！「{short}」搞定啦，+{earned} 根骨头！',
        f'真棒！「{short}」完成，骨头 +{earned}～',
        f'收到！「{short}」打卡成功，给你 {earned} 根骨头！',
    )
    speech = random.choice(cheers)
    message = f'完成任务！获得 {earned} 根骨头（总计 {bones}）'
    if labels:
        message += f' · 解锁：{"、".join(labels)}'
    return {
        'bones_earned': earned,
        'bones': bones,
        'tasks_completed': completed,
        'new_achievements': unlocked,
        'new_achievement_labels': labels,
        'speech': speech,
        'message': message + f'。骨头可用来喂桌宠（每次 {FEED_PET_COST} 根）。',
        'streak': ensure_streak(db),
    }


def spend_bones_feed_pet(cost: int | None = None) -> dict:
    """Spend bones to feed the desk pet and get a short cheer."""
    from ..database import store
    import random

    price = FEED_PET_COST if cost is None else int(cost)
    if price < 1:
        raise ValueError('Invalid bone cost')
    with store.connect() as db:
        streak = ensure_streak(db)
        bones = int(streak.get('bones') or 0)
        if bones < price:
            raise ValueError(f'骨头不够：喂豆豆需要 {price} 根，当前只有 {bones} 根。')
        bones -= price
        spent = int(streak.get('bones_spent') or 0) + price
        feeds = int(streak.get('pet_feeds') or 0) + 1
        achievements = list(streak.get('achievements') or [])
        unlocked = _append_achievements(achievements, [
            ('fed_pet', feeds >= 1),
            ('fed_pet_5', feeds >= 5),
        ])
        db.execute(
            'UPDATE study_streak SET bones=?, bones_spent=?, pet_feeds=?, achievements_json=? WHERE id=1',
            (bones, spent, feeds, json.dumps(achievements, ensure_ascii=False)),
        )
        db.commit()
        cheer = random.choice(PET_CHEERS)
        labels = [ACHIEVEMENT_LABELS.get(a, a) for a in unlocked]
        message = f'{cheer}（花费 {price} 根骨头，剩余 {bones}）'
        if labels:
            message += f' · 解锁：{"、".join(labels)}'
        return {
            'ok': True,
            'action': 'feed_pet',
            'cost': price,
            'bones': bones,
            'pet_feeds': feeds,
            # Short line for the floating pet bubble / talking animation.
            'speech': cheer,
            'message': message,
            'new_achievements': unlocked,
            'new_achievement_labels': labels,
            'streak': ensure_streak(db),
        }


def next_step(after: str | None = None, session_id=None) -> dict:
    """Return the next suggested action in the companion loop."""
    status = learning_status(session_id) if session_id else learning_status()
    if not status['has_documents']:
        return {
            'stage': 'upload',
            'action': 'upload',
            'title': '先上传一份学习资料',
            'suggestion': '把讲义或作业指南拖进知识库，我就能帮你抽关键词、讲重点。',
            'prompt': '打开知识库上传资料',
            'status': status,
        }
    if after == 'upload' or (after is None and status['open_tasks'] == 0 and not status['waiting_review']):
        if after != 'ask' and after != 'plan' and after != 'focus' and after != 'review':
            # Prefer ask-then-plan when no tasks yet.
            if status['open_tasks'] == 0 and after != 'overview':
                return {
                    'stage': 'ask',
                    'action': 'ask',
                    'title': '问出这份资料的重点',
                    'suggestion': '点一个关键词，或问「这份资料讲什么」。弄清重点后再做今日计划。',
                    'prompt': '这份资料讲什么',
                    'status': status,
                }
    if after in {'ask', 'overview'} or (status['open_tasks'] == 0 and not status['waiting_review']):
        if status['open_tasks'] == 0:
            return {
                'stage': 'plan',
                'action': 'plan',
                'title': '生成今日学习计划',
                'suggestion': '可以说：帮我制定复习这份资料的学习计划，1天每天30分钟。',
                'prompt': '帮我制定复习这份资料的学习计划，1天每天30分钟',
                'status': status,
            }
    focus = status['focus']
    if focus.get('id') and focus.get('remaining_seconds', 0) > 0:
        minutes = max(1, int(focus['remaining_seconds'] // 60))
        return {
            'stage': 'focus',
            'action': 'focus_wait',
            'title': '专注进行中',
            'suggestion': f'还剩约 {minutes} 分钟。结束后我们做一题复习巩固。',
            'prompt': '专注结束后开始复习',
            'status': status,
        }
    if status['waiting_review']:
        waiting = status['waiting_review']
        topic = (waiting.get('topic') or '').strip()
        stem = (waiting.get('stem') or waiting.get('question') or '').strip()
        # Drop decorative type tags for the coach card; keep the concrete ask.
        stem = re.sub(r'^【[^】]+】', '', stem).strip()
        preview = (stem[:96] + '…') if len(stem) > 96 else stem
        return {
            'stage': 'review',
            'action': 'review_answer',
            'title': f'继续复习：{topic}' if topic else '继续刚才的复习题',
            'suggestion': preview or '还有一题未作答，点下方到输入框直接写答案。',
            'prompt': '',
            'placeholder': f'关于「{topic}」，根据资料我认为……' if topic else '根据资料，我认为……',
            'status': status,
        }
    if after in {'plan', 'focus'} or status['open_tasks'] > 0:
        task = status['next_task']
        if task and after != 'review':
            return {
                'stage': 'focus',
                'action': 'focus',
                'title': '开始一段专注',
                'suggestion': f'下一步建议专注完成「{task["title"]}」，然后做一题复习。',
                'prompt': f'开始专注 {task.get("estimated_minutes") or 25} 分钟',
                'task': task,
                'status': status,
            }
    task = status['next_task']
    if task:
        return {
            'stage': 'focus',
            'action': 'focus',
            'title': '开始一段专注',
            'suggestion': f'下一步建议专注完成「{task["title"]}」，然后做一题复习。',
            'prompt': f'开始专注 {task.get("estimated_minutes") or 25} 分钟',
            'task': task,
            'status': status,
        }
    return {
        'stage': 'review',
        'action': 'review',
        'title': '做一题复习巩固',
        'suggestion': '可以说「开始复习」「今日小测」或「薄弱点回顾」，巩固刚才学过的内容。',
        'prompt': '薄弱点回顾',
        'status': status,
    }


def format_next_step(step: dict) -> str:
    title = step.get('title') or '下一步'
    suggestion = step.get('suggestion') or ''
    prompt = (step.get('prompt') or '').strip()
    placeholder = (step.get('placeholder') or '').strip()
    streak = (step.get('status') or {}).get('streak') or {}
    streak_note = ''
    current = int(streak.get('current_streak') or 0)
    if current >= 1:
        streak_note = f'\n连续学习 {current} 天，继续保持～'
    if prompt:
        tip = f'可以说：「{prompt}」'
    elif placeholder:
        tip = f'在输入框写：{placeholder}'
    else:
        tip = '在下方输入框继续即可。'
    return f'👉 下一步：{title}\n{suggestion}\n{tip}{streak_note}'


def today_plan(session_id=None) -> dict:
    """Concrete today's agenda from saved tasks — not a vague coach tip."""
    from ..database import store

    status = learning_status(session_id)
    with store.connect() as db:
        open_tasks = [task for task in store.list_tasks(db) if not task.get('done')]
    open_tasks.sort(key=lambda task: (task.get('scheduled_day') is None, task.get('scheduled_day') or 0, task.get('id') or 0))

    if not open_tasks:
        if not status.get('has_documents'):
            step = {
                'stage': 'upload',
                'action': 'upload',
                'title': '先上传学习资料',
                'suggestion': '还没有今日计划。上传资料后，我可以按资料帮你排今天的任务。',
                'prompt': '打开知识库上传资料',
                'status': status,
            }
            return {
                'text': '📅 今日计划\n还没有任务。\n\n先上传一份学习资料，再点「今日计划」，我就能帮你排今天的安排。',
                'next_step': step,
                'tasks': [],
                'needs_plan': False,
                'day': None,
            }
        step = {
            'stage': 'plan',
            'action': 'plan',
            'title': '生成今日学习计划',
            'suggestion': '资料已在，但还没有保存任务。正在为你生成 1 天计划草稿。',
            'prompt': '帮我制定复习这份资料的学习计划，1天每天30分钟',
            'status': status,
        }
        return {
            'text': '📅 今日计划\n还没有待办。\n点「今日计划」时我会按资料自动排好今日提醒，完成后就能在气泡里打卡领骨头。',
            'next_step': step,
            'tasks': [],
            'needs_plan': True,
            'day': None,
        }

    days = [int(task['scheduled_day']) for task in open_tasks if task.get('scheduled_day')]
    today_day = min(days) if days else None
    if today_day is not None:
        today_tasks = [task for task in open_tasks if task.get('scheduled_day') == today_day]
        undated = [task for task in open_tasks if not task.get('scheduled_day')]
        today_tasks = today_tasks + undated
        later = [task for task in open_tasks if task.get('scheduled_day') and int(task['scheduled_day']) != today_day]
        head = f'📅 今日事办（第 {today_day} 天）'
    else:
        today_tasks = open_tasks
        later = []
        head = '📅 今日事办提醒'

    lines = [head, '']
    total = 0
    public_tasks = []
    for index, task in enumerate(today_tasks, 1):
        minutes = int(task.get('estimated_minutes') or 0)
        total += minutes
        title = task.get('title') or '未命名任务'
        suffix = f'（约 {minutes} 分钟）' if minutes else ''
        lines.append(f'{index}. {title}{suffix}')
        public_tasks.append({
            'id': task.get('id'),
            'title': title,
            'estimated_minutes': minutes,
            'scheduled_day': task.get('scheduled_day'),
            'done': False,
        })
    if total:
        lines.append('')
        lines.append(f'合计约 {total} 分钟 · 共 {len(today_tasks)} 项')
    if later:
        lines.append(f'后续还有 {len(later)} 项未完成（第 {min(int(t["scheduled_day"]) for t in later)} 天起）。')

    first = today_tasks[0]
    focus_minutes = int(first.get('estimated_minutes') or 25) or 25
    step = {
        'stage': 'focus',
        'action': 'focus',
        'title': f'开始做：{first.get("title") or "今日第一项"}',
        'suggestion': f'选一项确认内容后开始打卡；计时结束后豆豆会给你骨头。',
        'prompt': f'开始专注 {focus_minutes} 分钟',
        'task': first,
        'status': status,
    }
    lines.append('')
    lines.append('选一项确认后点「开始打卡」；计时中可说「我做完了」提前领骨头。要改内容就跟我说或去完整窗口。')
    return {
        'text': '\n'.join(lines).strip(),
        'next_step': step,
        'tasks': public_tasks,
        'needs_plan': False,
        'day': today_day,
    }
