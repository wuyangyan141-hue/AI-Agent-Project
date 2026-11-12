"""Coach the next step in the study loop without requiring a model key."""
from __future__ import annotations

import json
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
            "SELECT id, topic, question, status FROM review_sessions WHERE session_id IS ? ORDER BY id LIMIT 8",(session_id,)
        ).fetchall()
        waiting_review = next((dict(row) for row in reviews if row['status'] == 'waiting'), None)
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
    row = db.execute('SELECT * FROM study_streak WHERE id=1').fetchone()
    if row is None:
        db.execute('INSERT INTO study_streak(id, current_streak, total_focus_minutes) VALUES (1, 0, 0)')
        db.commit()
        row = db.execute('SELECT * FROM study_streak WHERE id=1').fetchone()
    data = dict(row)
    try:
        data['achievements'] = json.loads(data.get('achievements_json') or '[]')
    except Exception:
        data['achievements'] = []
    return data


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
        for badge, ok in (
            ('first_focus', total >= 1),
            ('focus_60', total >= 60),
            ('streak_3', current >= 3),
        ):
            if ok and badge not in achievements:
                achievements.append(badge)
        db.execute(
            'UPDATE study_streak SET current_streak=?, last_study_date=?, total_focus_minutes=?, achievements_json=? WHERE id=1',
            (current, today, total, json.dumps(achievements, ensure_ascii=False)),
        )
        db.commit()
        return ensure_streak(db)


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
        topic = status['waiting_review']['topic']
        question = (status['waiting_review'].get('question') or '').strip()
        preview = (question[:42] + '…') if len(question) > 42 else question
        return {
            'stage': 'review',
            'action': 'review_answer',
            'title': '继续刚才的复习题',
            'suggestion': (
                f'主题：{topic}。'
                + (f'题目：{preview}。' if preview else '')
                + '请在输入框直接作答；评分按是否覆盖要点，不是词频。'
            ),
            'prompt': '',
            'placeholder': f'关于「{topic}」，结合资料我觉得……',
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
        'suggestion': '可以说「开始复习」或「今日小测」，巩固刚才学过的内容。',
        'prompt': '开始复习今日重点',
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
