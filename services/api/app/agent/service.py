"""LangChain agent when configured; deterministic study demo otherwise."""
import os
from collections.abc import Callable
from typing import Awaitable
from langchain.agents import create_agent
from langchain.mcp import MCPAdapter
from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from . import prompts
from .intent import StudyIntent, explicit_intent
from ..database.store import list_tasks
from ..skills.study_plan import PlanProposal, make_study_plan, validate_plan
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
            def preview_study_plan(goal: str, days: int = 3, minutes_per_day: int = 45) -> str:
                """Preview a study plan for a goal without saving tasks; user must confirm in the UI."""
                return str([step.__dict__ for step in make_study_plan(goal, days, minutes_per_day)])
            @tool
            def preview_unfinished_replan(days: int, minutes_per_day: int) -> str:
                """Preview a schedule for unfinished tasks without changing any task."""
                with db_factory() as db:
                    return str(propose_replan(list_tasks(db), days, minutes_per_day))
            self.local_tools = [preview_study_plan, preview_unfinished_replan]

    async def detect_intent(self, text: str, history: list[dict[str, str]]) -> StudyIntent:
        direct = explicit_intent(text)
        if direct.action != 'chat' or self.mode != 'langchain':
            return direct
        model_name = os.getenv('AGENT_MODEL', 'openai:gpt-4o-mini').removeprefix('openai:')
        classifier = ChatOpenAI(model=model_name, temperature=0).with_structured_output(StudyIntent)
        result = await classifier.ainvoke([
            ('system', '识别用户当前意图。只有明确要求制定学习计划时选 plan；明确要重新安排未完成任务时选 replan；其他选 chat。'
             'goal 填学习主题，不要编造；缺少天数用 3，缺少每天时长用 45 分钟。'),
            *[(item['role'], item['content']) for item in history[-4:]],
            ('user', text),
        ])
        return result if isinstance(result, StudyIntent) else StudyIntent.model_validate(result)

    async def generate_plan(self, goal: str, days: int, minutes_per_day: int):
        """Generate a draft, then enforce the schedule before any persistence."""
        # Validate input even when the model is enabled.
        make_study_plan(goal, days, minutes_per_day)
        if self.mode != 'langchain':
            return make_study_plan(goal, days, minutes_per_day)
        model_name = os.getenv('AGENT_MODEL', 'openai:gpt-4o-mini').removeprefix('openai:')
        planner = ChatOpenAI(model=model_name, temperature=0).with_structured_output(PlanProposal)
        result = await planner.ainvoke([
            ('system', '你是学习计划制定者。给出可操作且不重复的学习任务，每天至少一个任务。'
             '只按用户给定天数安排，不得超过每天时间预算。不要声称任务已保存。'),
            ('user', f'学习目标：{goal}\n天数：{days}\n每天最多：{minutes_per_day} 分钟'),
        ])
        proposal = result if isinstance(result, PlanProposal) else PlanProposal.model_validate(result)
        return validate_plan(proposal, days, minutes_per_day)

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
