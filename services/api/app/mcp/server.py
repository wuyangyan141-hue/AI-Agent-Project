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
def start_focus_timer(minutes: int = 25, task_id: int | None = None) -> dict:
    """Start a focus timer; at most one timer is active."""
    if not 1 <= minutes <= 240:
        raise ValueError('Invalid duration')
    with store.connect() as db:
        result = store.start_focus(db, task_id, minutes)
    if result is None:
        raise ValueError('Task not found')
    return result

@mcp.tool()
def get_focus_timer() -> dict:
    """Return the active focus timer and remaining seconds."""
    with store.connect() as db:
        return store.focus_status(db) or {'id': None, 'remaining_seconds': 0}

if __name__ == '__main__':
    mcp.run(transport='stdio')
