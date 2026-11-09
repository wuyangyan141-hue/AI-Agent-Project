from app.mcp.server import mcp

def test_mcp_server_registers_tool():
    assert mcp.name == 'learning-companion-tools'
