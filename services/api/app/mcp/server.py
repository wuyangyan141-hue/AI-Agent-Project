"""MCP SDK tool server; run: python -m app.mcp.server (stdio)."""
from mcp.server import MCPServer
from ..database.store import connect, list_tasks

mcp = MCPServer('learning-companion-tools')

@mcp.tool()
def list_study_tasks() -> list[dict]:
    """Return saved study tasks and their completion state."""
    with connect() as db:
        return list_tasks(db)

if __name__ == '__main__':
    mcp.run(transport='stdio')
