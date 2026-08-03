"""LLM Ops — the trace → eval → gate → release self-improvement loop.

* registry     — versioned prompts/config with an active version + a canary candidate.
* evaluate     — automatic per-run scores (faithfulness, relevancy) pushed to Langfuse.
* agent_eval   — per-specialist scores, so a weak run attributes to a specific agent.
* claim_verify — claim-level citation verification (does the evidence support the claim?).
* gate         — threshold check (did it pass?) + a diagnosis of why not.
* optimizer    — if the gate fails: diagnose → rewrite the prompt → re-run → re-eval →
                 release the improved version only if it actually scores better.
"""

from .agent_eval import evaluate_agents, score_agent, weakest_agent
from .claim_verify import verify_claim, verify_claims
from .gate import GateResult, run_gate
from .optimizer import optimize
from .registry import PromptRegistry, get_registry

__all__ = [
    "GateResult",
    "PromptRegistry",
    "evaluate_agents",
    "get_registry",
    "optimize",
    "run_gate",
    "score_agent",
    "verify_claim",
    "verify_claims",
    "weakest_agent",
]
