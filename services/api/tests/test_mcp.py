from app.mcp.server import mcp
from langchain.mcp import MCPAdapter
import asyncio

def test_mcp_server_registers_tool():
    assert mcp.name == 'learning-companion-tools'


def test_langchain_adapter_invokes_mcp_read_tools(tmp_path, monkeypatch):
    monkeypatch.setenv('DATABASE_PATH', str(tmp_path / 'mcp-adapter.db'))
    async def check():
        async with MCPAdapter(mcp) as adapter:
            tools = {item.name: item for item in await adapter.list_tools()}
            assert {'list_study_tasks', 'get_focus_timer'} <= tools.keys()
            assert '[]' in str(await tools['list_study_tasks'].ainvoke({}))
            assert 'remaining_seconds' in str(await tools['get_focus_timer'].ainvoke({}))
    asyncio.run(check())
