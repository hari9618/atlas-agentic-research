---
name: atlas-langgraph-node
description: >
  Add a LangGraph node, specialist agent, debate participant, or MCP tool to the
  Atlas graph the Atlas way — typed shared state, the shared Groq LLM factory,
  Langfuse callbacks on every invocation, evidence-grounded outputs with provenance,
  and the SQLite checkpointer. Use when the orchestration-engineer extends
  atlas/core/{graph,agents,tools}. Primarily for the orchestration-engineer subagent.
---

# Skill: Atlas LangGraph node / agent / tool

## 1. Know the shared state
The graph state is the "research scratchpad". Extend it additively; use reducers
for fields multiple agents append to (e.g. findings).
```python
from typing import Annotated, TypedDict
import operator

class ResearchState(TypedDict):
    query: str
    plan: list[str]
    findings: Annotated[list[dict], operator.add]   # specialists append
    debate: Annotated[list[dict], operator.add]      # bull/bear turns
    report: str | None
    confidence: float | None
```

## 2. Write a node (agent)
```python
from ..llm import get_llm
from ..observability import langchain_callbacks

def fundamentals_agent(state: ResearchState) -> dict:
    llm = get_llm(temperature=0.2)           # ~0 for Judge, hotter for debaters
    # retrieve grounded evidence (with provenance) via the rag layer first
    msgs = [...]
    resp = llm.invoke(msgs, config={"callbacks": langchain_callbacks()})
    # return ONLY grounded claims, each tagged with its citation
    return {"findings": [{"agent": "fundamentals", "claim": ..., "citation": ...}]}
```

## 3. Wire it into the graph
```python
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver

g = StateGraph(ResearchState)
g.add_node("fundamentals", fundamentals_agent)
g.add_edge(START, "supervisor")
# supervisor fans out to specialists, then → debate → synthesizer → END
graph = g.compile(checkpointer=SqliteSaver.from_conn_string("atlas_checkpoints.db"))
```

## 4. MCP tools
- Expose external calls (`web_search`, `sec_edgar`, `stock_data`, `company_news`)
  through the MCP tool server; agents call them as tools. Keep each tool small,
  typed, and free-tier friendly.

## 5. Non-negotiables (from CLAUDE.md)
- Use `get_llm()`; set temperature per role (debaters hot, Judge ≈ 0).
- Attach `langchain_callbacks()` to **every** LLM/tool invocation → Langfuse spans.
- Agents may only assert evidence-grounded claims; carry provenance through state
  so the synthesizer can cite. No free-handed facts.
- Compile with the checkpointer so runs are durable/resumable.

## 6. Verify & report
- Provide a tiny isolated invocation (or test) of the new node.
- Report nodes/edges added, state fields touched, and how it appears in Langfuse.
