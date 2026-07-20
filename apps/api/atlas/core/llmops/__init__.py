"""LLM Ops — the trace → eval → gate → release self-improvement loop.

* registry   — versioned prompts/config with an active version + a canary candidate.
* evaluate   — automatic per-run scores (faithfulness, relevancy) pushed to Langfuse.
* agent_eval — per-specialist scores, so a weak run attributes to a specific agent.
* gate       — threshold check (did it pass?) + a diagnosis of why not.
* optimizer  — if the gate fails: diagnose → rewrite the prompt → re-run → re-eval →
               release the improved version only if it actually scores better.
"""

from .agent_eval import evaluate_agents, score_agent, weakest_agent
from .gate import GateResult, run_gate
from .optimizer import optimize
from .registry import PromptRegistry, get_registry

__all__ = [
    "PromptRegistry", "get_registry", "run_gate", "GateResult", "optimize",
    "evaluate_agents", "score_agent", "weakest_agent",
]
