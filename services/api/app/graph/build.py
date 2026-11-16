"""Compile LangGraph study subgraphs."""
from __future__ import annotations

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from .nodes import plan_collect, plan_run, quiz_collect, quiz_run
from .state import CompanionState

_checkpointer = MemorySaver()
_quiz_graph = None
_plan_graph = None


def _compile_quiz():
    g = StateGraph(CompanionState)
    g.add_node('collect', quiz_collect)
    g.add_node('run', quiz_run)
    g.add_edge(START, 'collect')
    g.add_edge('collect', 'run')
    g.add_edge('run', END)
    return g.compile(checkpointer=_checkpointer)


def _compile_plan():
    g = StateGraph(CompanionState)
    g.add_node('collect', plan_collect)
    g.add_node('run', plan_run)
    g.add_edge(START, 'collect')
    g.add_edge('collect', 'run')
    g.add_edge('run', END)
    return g.compile(checkpointer=_checkpointer)


def quiz_graph():
    global _quiz_graph
    if _quiz_graph is None:
        _quiz_graph = _compile_quiz()
    return _quiz_graph


def plan_graph():
    global _plan_graph
    if _plan_graph is None:
        _plan_graph = _compile_plan()
    return _plan_graph