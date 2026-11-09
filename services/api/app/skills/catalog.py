"""Reusable workflow contract with explicit input and output schemas later."""
from typing import Protocol

class Skill(Protocol):
    name: str
    async def run(self, inputs: dict) -> dict: ...
