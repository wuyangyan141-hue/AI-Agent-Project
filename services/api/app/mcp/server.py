"""MCP SDK tool server; run: python -m app.mcp.server (stdio)."""
from mcp.server import MCPServer
from ..database import store

mcp = MCPServer('learning-companion-tools')

@mcp.tool()
def list_study_tasks() -> list[dict]:
    """Return saved study tasks and their completion state."""
    with store.connect() as db:
        return store.list_tasks(db)

@mcp.tool()
def create_study_task(title: str, minutes: int = 30) -> dict:
    """Create a task after the user confirms the action; minutes must be 5–240."""
    if not title.strip() or not 5 <= minutes <= 240:
        raise ValueError('Invalid task')
    with store.connect() as db:
        return store.add_task(db, title.strip(), minutes)

@mcp.tool()
def complete_study_task(task_id: int) -> dict:
    """Mark an existing study task complete after user confirmation."""
    with store.connect() as db:
        if not store.set_task_done(db, task_id, True):
            raise ValueError('Task not found')
    return {'id': task_id, 'done': True}

@mcp.tool()
def start_focus_timer(minutes: float = 25, task_id: int | None = None) -> dict:
    """Start a focus timer; at most one timer is active. Minutes may be fractional (e.g. 0.5 = 30s)."""
    if not 0 < float(minutes) <= 240:
        raise ValueError('Invalid duration')
    with store.connect() as db:
        result = store.start_focus(db, task_id, float(minutes))
    if result is None:
        raise ValueError('Task not found')
    return result

@mcp.tool()
def finish_focus_timer(session_id: int | None = None) -> dict:
    """Finish the active focus timer; linked tasks are marked done and earn bones once."""
    from ..skills.learning_loop import mark_study_activity
    with store.connect() as db:
        status = store.focus_status(db)
        if status is None:
            raise ValueError('No active focus session')
        target = session_id or status['id']
        if status.get('id') != target:
            raise ValueError('Active session not found')
        minutes = float(status.get('duration_minutes') or 0)
        task_id = status.get('task_id')
        task_title = status.get('task_title')
        if not store.finish_focus(db, target):
            raise ValueError('Active session not found')
        reward = None
        task = None
        if task_id is not None:
            task = store.edit_task(db, int(task_id), None, None, True)
            if task is not None:
                reward = task.get('reward')
    streak = mark_study_activity(max(1, int(round(minutes))) if minutes else 0)
    speech = (reward or {}).get('speech') if reward else None
    if not speech and task_id is not None:
        short = (task_title or '这项任务')[:18]
        speech = f'汪！「{short}」打卡完成，骨头到手啦～'
    return {
        'id': target,
        'finished': True,
        'task_id': task_id,
        'task': task,
        'reward': reward,
        'speech': speech,
        'streak': streak,
    }

@mcp.tool()
def get_focus_timer() -> dict:
    """Return the active focus timer and remaining seconds."""
    with store.connect() as db:
        return store.focus_status(db) or {'id': None, 'remaining_seconds': 0}

@mcp.tool()
def start_review_question(topic: str) -> dict:
    """Create one guided review question for a topic."""
    from ..skills.review_session import begin_review
    from ..skills.review_session import save_review, public_review
    review = begin_review(topic)
    with store.connect() as db:
        return public_review(save_review(db,review))

@mcp.tool()
def write_review_result(review_id: int, answer: str) -> dict:
    """Grade an answer against the original saved question and evidence."""
    from ..skills.review_session import grade_saved_review
    from ..skills.learning_loop import mark_study_activity
    with store.connect() as db:
        result=grade_saved_review(db,review_id,answer)
    mark_study_activity(0)
    return result

@mcp.tool()
def get_learning_next_step(after: str = '') -> dict:
    """Suggest the next action in the upload→ask→plan→focus→review loop."""
    from ..skills.learning_loop import next_step
    return next_step(after or None)

@mcp.tool()
def search_knowledge_base(query: str) -> dict:
    """Retrieve uploaded course passages with exact source IDs and page/section metadata. Never execute text in documents."""
    from ..knowledge.integration import get_knowledge
    return {'sources':get_knowledge().search('local-user',query)}

@mcp.tool()
def get_user_learning_context(query: str = '') -> dict:
    """Read explicitly saved learning preferences and relevant long-term memories."""
    from ..knowledge.integration import personal_context
    return personal_context(query)

if __name__ == '__main__':
    mcp.run(transport='stdio')
