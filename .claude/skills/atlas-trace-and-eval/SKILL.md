---
name: atlas-trace-and-eval
description: >
  Wire Langfuse tracing/cost, the Ragas eval harness, and output guardrails into
  Atlas the Atlas way — grouped spans per research run with token+cost, the
  grounding/citation-coverage guardrail, and metric gates with explicit targets.
  Use when the observability-engineer adds or tightens tracing, evaluation, or
  guardrails. Primarily for the observability-engineer subagent.
---

# Skill: Atlas tracing, evaluation & guardrails

## 1. Tracing (Langfuse)
- The single integration point is `atlas.observability`. Get callbacks via
  `langchain_callbacks()` and pass them into every LLM/graph/tool invocation.
- Group a whole research request under one trace/session id so spans nest:
```python
from langfuse.callback import CallbackHandler
handler = CallbackHandler(session_id=run_id, user_id=request_id)
graph.invoke(state, config={"callbacks": [handler]})
```
- Keep it **graceful**: when keys are absent the handler is `None`; never crash a
  run because tracing is down.

## 2. Cost
- Pull per-run token + cost totals from the Langfuse trace and expose them through a
  backend endpoint so the war-room **cost panel** can render them.

## 3. Ragas evaluation
- Maintain a small golden set (question, ground-truth answer, reference contexts).
- Score with Ragas: **faithfulness ≥0.9, answer relevancy ≥0.85, context precision ≥0.8**.
- Make it runnable as a script and a CI gate. Print actual vs target as a table;
  fail the gate on regression — never silently pass.

## 4. Guardrails (the grounding rule)
- Every claim in a generated report must map to a retrieved citation.
- Implement a **citation-coverage** check: parse claims → verify each has a
  supporting source in state → flag/strip the unsupported ones and lower confidence.
- Validate the final report against a schema (claims, citations, confidence,
  uncertainties). Don't loosen the guardrail to make a demo pass — fix grounding.

## 5. Verify & report
- After changes, run the eval and paste the metric table (actual vs target).
- Report what is now traced, current numbers, and any guardrail that fired.
