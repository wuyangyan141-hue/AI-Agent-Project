"""LangChain agent when configured; deterministic study demo otherwise."""
import os
from collections.abc import Callable
from langchain.agents import create_agent
from langchain_core.tools import tool
from . import prompts
from ..database.store import list_tasks


class StudyAgent:
    def __init__(self, db_factory: Callable):
        self.db_factory = db_factory
        self.mode = 'langchain' if os.getenv('OPENAI_API_KEY') else 'demo'
        self.runner = None
        if self.mode == 'langchain':
            @tool
            def list_study_tasks() -> str:
                """List the user's saved study tasks and completion state."""
                with db_factory() as db:
                    return str(list_tasks(db))
            self.runner = create_agent(
                model=os.getenv('AGENT_MODEL', 'openai:gpt-4o-mini'),
                tools=[list_study_tasks],
                system_prompt=prompts.SYSTEM_PROMPT,
            )

    async def respond(self, text: str, history: list[dict[str, str]]) -> str:
        if self.runner is None:
            return f'收到：{text}。先定一个 20 分钟的小目标，然后告诉我你要从哪一步开始。'
        result = await self.runner.ainvoke({'messages': history + [{'role': 'user', 'content': text}]})
        content = result['messages'][-1].content
        return content if isinstance(content, str) else str(content)
