"""Agent orchestration seam. Replace EchoAgent with LangChain model/tools later."""
from typing import Protocol

class Agent(Protocol):
    async def respond(self, text: str) -> str: ...

class EchoAgent:
    async def respond(self, text: str) -> str:
        return f"收到：{text}。我们可以把它拆成一个小目标。"
