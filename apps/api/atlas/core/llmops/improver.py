"""The learning loop: diagnose → propose → replay → decide → release → watch.

1. **Diagnose** recent run records into attributed failure patterns, human review
   weighted highest (``diagnose``).
2. **Propose** one bounded change to the responsible component's policy: a lesson,
   deeper retrieval, or exemplars (``proposer``).
3. **Replay** baseline vs candidate on the same inputs over several recent questions
   (``replay``).
4. **Decide** with a paired rule: enough trials, a real mean gain, and no question
   made materially worse. A lucky single re-roll can't pass.
5. **Release** as a new immutable policy version, or reject. Either way the
   experiment (hypothesis, change, every trial, decision) is stored.
6. **Watch**: after every recorded run, a released version whose live scores fall
   below its predecessor's is rolled back automatically.

Nothing here runs on the user's request path except the cheap ``check_regressions``.
"""

from __future__ import annotations

import logging
import uuid
from statistics import mean

from .diagnose import open_issues
from .policy import COMPONENTS, LABELS, PolicyStore, get_policies
from .proposer import propose
from .records import RunRecords, get_records
from .replay import PairRunner, Trial, benchmark, paired_trials, run_pair
from .store import DocumentStore, now_iso

log = logging.getLogger("atlas.llmops.improver")

BENCHMARK_SIZE = 3      # questions (distinct companies) per experiment
MIN_TRIALS = 2          # fewer paired trials than this is not evidence
MIN_GAIN = 0.03         # mean paired improvement required to release
MAX_REGRESSION = 0.10   # no single question may get worse than this
RECENT_RECORDS = 40
ROLLBACK_MIN_RUNS = 3   # live runs needed on each version before comparing
ROLLBACK_DROP = 0.08    # live mean drop that triggers an automatic rollback
_RETRY_AFTER = 5        # a rejected (component, kind) is skipped for this many experiments

_experiments: DocumentStore | None = None


def get_experiments() -> DocumentStore:
    global _experiments
    if _experiments is None:
        _experiments = DocumentStore("experiment", keep=200)
    return _experiments


def reset_experiments() -> None:
    global _experiments
    _experiments = None


def decide(trials: list[Trial]) -> tuple[bool, float, str]:
    """``(release?, mean delta, reason)`` under the paired decision rule."""
    if len(trials) < MIN_TRIALS:
        return False, 0.0, f"only {len(trials)} usable trial(s); need {MIN_TRIALS}"
    deltas = [t.delta for t in trials]
    gain = round(mean(deltas), 3)
    worst = min(deltas)
    if worst < -MAX_REGRESSION:
        return False, gain, (f"made one question worse by {-worst:.2f} "
                             f"(limit {MAX_REGRESSION:.2f})")
    if gain < MIN_GAIN:
        return False, gain, f"mean gain {gain:+.3f} is below the {MIN_GAIN:.2f} bar"
    return True, gain, f"mean gain {gain:+.3f} across {len(trials)} questions, no regression"


def improve(*, records: RunRecords | None = None, policies: PolicyStore | None = None,
            experiments: DocumentStore | None = None, runner: PairRunner = run_pair) -> dict:
    """Run ONE experiment on the highest-weight open issue. Returns
    ``{"experiment": dict | None, "message": str}``."""
    records = records or get_records()
    policies = policies or get_policies()
    experiments = experiments or get_experiments()

    recent = records.recent(RECENT_RECORDS)
    active = {c: policies.active(c) for c in COMPONENTS}
    issues = open_issues(recent, active)
    if not issues:
        return {"experiment": None,
                "message": "No open failure patterns in recent runs — nothing to improve."}

    blocked = {(e.get("component"), e.get("issue_kind"))
               for e in experiments.list(_RETRY_AFTER) if e.get("decision") == "rejected"}
    issue = proposal = None
    for candidate_issue in issues:
        if (candidate_issue["component"], candidate_issue["kind"]) in blocked:
            continue
        proposal = propose(candidate_issue, active[candidate_issue["component"]], recent)
        if proposal is not None:
            issue = candidate_issue
            break
    if proposal is None or issue is None:
        return {"experiment": None,
                "message": "Every open issue was tried recently or has no new fix to test."}

    comp = proposal.component
    bench = benchmark(recent, BENCHMARK_SIZE, prefer=issue.get("records"))
    if len(bench) < MIN_TRIALS:
        return {"experiment": None,
                "message": f"Need recorded runs on at least {MIN_TRIALS} different companies "
                           "to test a change fairly."}

    trials = paired_trials(comp, active[comp], proposal.policy, bench, runner=runner)
    released, gain, reason = decide(trials)
    version_before = policies.active_version(comp)
    version_after = None
    hypothesis = (f"{LABELS[comp]}: {issue['kind'].replace('_', ' ')} "
                  f"({issue['count']}× recently, e.g. “{issue['example'][:140]}”)")
    if released:
        version_after = policies.release(
            comp, proposal.policy,
            notes=f"experiment: {proposal.summary} ({gain:+.3f})")

    experiment = {
        "id": f"exp-{uuid.uuid4().hex[:10]}",
        "created_at": now_iso(),
        "component": comp,
        "issue_kind": issue["kind"],
        "lever": proposal.lever,
        "hypothesis": hypothesis,
        "change": {"summary": proposal.summary, "before": proposal.before,
                   "after": proposal.after},
        "trials": [t.to_dict() for t in trials],
        "mean_delta": gain,
        "decision": "released" if released else "rejected",
        "reason": reason,
        "version_before": version_before,
        "version_after": version_after,
    }
    experiments.put(experiment["id"], experiment)
    log.info("experiment %s on %s (%s): %s — %s", experiment["id"], comp, proposal.lever,
             experiment["decision"], reason)
    message = (f"Released {LABELS[comp]} v{version_after}: {reason}." if released
               else f"Kept {LABELS[comp]} v{version_before}: {reason}.")
    return {"experiment": experiment, "message": message}


def _live_mean(records: list[dict], comp: str, version: int) -> tuple[float | None, int]:
    vals = [r["scores"]["overall"] for r in records
            if (r.get("policy_versions") or {}).get(comp) == version
            and (r.get("scores") or {}).get("overall") is not None]
    return (round(mean(vals), 3) if vals else None), len(vals)


def check_regressions(*, records: RunRecords | None = None,
                      policies: PolicyStore | None = None,
                      experiments: DocumentStore | None = None) -> list[dict]:
    """Roll back any released version that live runs score worse than its predecessor.

    Cheap (no LLM): reads scores already on the run records. Returns rollback events.
    """
    records = records or get_records()
    policies = policies or get_policies()
    experiments = experiments or get_experiments()
    recent = records.recent(120)
    events = []
    for comp in COMPONENTS:
        versions = policies.versions(comp)
        active_v = policies.active_version(comp)
        current = next((v for v in versions if v["version"] == active_v), None)
        previous = (current or {}).get("previous")
        if previous is None or not str(current.get("notes", "")).startswith("experiment"):
            continue
        new_mean, n_new = _live_mean(recent, comp, active_v)
        old_mean, n_old = _live_mean(recent, comp, previous)
        if (n_new < ROLLBACK_MIN_RUNS or n_old < ROLLBACK_MIN_RUNS
                or new_mean is None or old_mean is None):
            continue
        if new_mean < old_mean - ROLLBACK_DROP:
            restored = policies.rollback(comp)
            event = {
                "id": f"rb-{uuid.uuid4().hex[:10]}", "created_at": now_iso(),
                "component": comp, "issue_kind": "live_regression", "lever": "rollback",
                "hypothesis": f"{LABELS[comp]} v{active_v} scored worse in live runs",
                "change": {"summary": f"Automatic rollback to v{restored}",
                           "before": f"v{active_v}", "after": f"v{restored}"},
                "trials": [], "mean_delta": round(new_mean - old_mean, 3),
                "decision": "rolled_back",
                "reason": (f"live mean {new_mean:.3f} over {n_new} runs vs {old_mean:.3f} over "
                           f"{n_old} runs on v{previous}"),
                "version_before": active_v, "version_after": restored,
            }
            experiments.put(event["id"], event)
            events.append(event)
            log.warning("auto-rollback %s v%d → v%d (%s)", comp, active_v, restored,
                        event["reason"])
    return events


def overview(*, records: RunRecords | None = None, policies: PolicyStore | None = None,
             experiments: DocumentStore | None = None) -> dict:
    """Everything the Learning page shows, in one read."""
    records = records or get_records()
    policies = policies or get_policies()
    experiments = experiments or get_experiments()
    recent = records.recent(RECENT_RECORDS)
    active = {c: policies.active(c) for c in COMPONENTS}
    components = []
    for c in COMPONENTS:
        versions = policies.versions(c)
        v = policies.active_version(c)
        updated = next((x["created_at"] for x in versions if x["version"] == v), None)
        components.append({"name": c, "label": LABELS[c], "version": v,
                           "lessons": active[c].lessons, "exemplars": len(active[c].exemplars),
                           "top_k": active[c].top_k, "updated_at": updated})
    issues = [{k: i[k] for k in ("component", "kind", "count", "example", "lever", "weight")}
              for i in open_issues(recent, active)[:8]]
    return {"components": components, "runs": records.stats(), "issues": issues,
            "experiments": experiments.list(10)}
