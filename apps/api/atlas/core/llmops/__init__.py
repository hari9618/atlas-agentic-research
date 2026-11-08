"""LLM Ops — evaluation and the self-improving learning loop.

* evaluate      — automatic per-run scores (faithfulness, relevancy, ...) → Langfuse.
* agent_eval    — per-specialist scores, so a weak run is attributed to one agent.
* claim_verify / report_verify — claim- and statement-level grounding checks.
* gate          — release thresholds for a run.
* records       — one record per finished run: scores + the human review outcome.
* policy        — versioned, bounded, learnable agent policies (lessons, exemplars,
                  retrieval depth) with release and rollback.
* diagnose → proposer → replay → improver — the loop: attribute failures, propose
  one change, replay it against the baseline on the same inputs, release only on a
  paired gain, roll back automatically on a live regression.

Submodules are imported where used; this package stays import-light.
"""
