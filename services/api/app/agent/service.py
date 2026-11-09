"""LangChain agent when configured; deterministic study demo otherwise."""
import os
from collections.abc import Callable
from typing import Awaitable
from langchain.agents import create_agent
from langchain.mcp import MCPAdapter
from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.tools import tool
from . import prompts
from ..database.store import list_tasks
from ..skills.study_plan import make_study_plan
from ..skills.replan import propose_replan
from ..mcp.server import mcp


class ToolStatusHandler(AsyncCallbackHandler):
    def __init__(self, emit: Callable[[str, str], Awaitable[None]]):
        self.emit = emit

    async def on_tool_start(self, serialized: dict, input_str: str, **kwargs) -> None:
        name = serialized.get('name') or kwargs.get('name') or 'tool'
        await self.emit('tool', f'正在调用工具：{name}')


class StudyAgent:
    def __init__(self, db_factory: Callable):
        self.db_factory = db_factory
        self.mode = 'langchain' if os.getenv('OPENAI_API_KEY') else 'demo'
        self.local_tools = []
        if self.mode == 'langchain':
            @tool
            def list_study_tasks() -> str:
                """List the user's saved study tasks and completion state."""
                with db_factory() as db:
                    return str(list_tasks(db))
            @tool
            def preview_study_plan(goal: str, days: int = 3, minutes_per_day: int = 45) -> str:
                """Preview a study plan for a goal without saving tasks; user must confirm in the UI."""
                return str([step.__dict__ for step in make_study_plan(goal, days, minutes_per_day)])
            @tool
            def preview_unfinished_replan(days: int, minutes_per_day: int) -> str:
                """Preview a schedule for unfinished tasks without changing any task."""
                with db_factory() as db:
                    return str(propose_replan(list_tasks(db), days, minutes_per_day))
            self.local_tools = [preview_study_plan, preview_unfinished_replan]

    async def respond(self, text: str, history: list[dict[str, str]], emit: Callable[[str, str], Awaitable[None]] | None = None) -> str:
        if self.mode != 'langchain':
            return f'收到：{text}。先定一个 20 分钟的小目标，然后告诉我你要从哪一步开始。'
        # Keep the MCP connection alive for the full agent invocation. Writes require
        # a separate user confirmation in the UI and are never exposed to the model.
        async with MCPAdapter(mcp) as adapter:
            mcp_tools = [tool for tool in await adapter.list_tools()
                         if tool.name in {'list_study_tasks', 'get_focus_timer'}]
            runner = create_agent(
                model=os.getenv('AGENT_MODEL', 'openai:gpt-4o-mini'),
                tools=[*mcp_tools, *self.local_tools],
                system_prompt=prompts.SYSTEM_PROMPT,
            )
            config = {'callbacks': [ToolStatusHandler(emit)]} if emit else None
            result = await runner.ainvoke({'messages': history + [{'role': 'user', 'content': text}]}, config=config)
        content = result['messages'][-1].content
        return content if isinstance(content, str) else str(content)
