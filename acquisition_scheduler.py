"""Deterministic, dry-run-only acquisition state derivation."""

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, List

from acquisition import AcquisitionPlan


@dataclass(frozen=True)
class DryRunEvaluation:
    identity: str
    state: str
    plan: AcquisitionPlan
    operation: dict
    reason: str = ""


def plan_identity(plan: AcquisitionPlan) -> str:
    return f"{plan.event_id}:{plan.surface_id}:{plan.feed_mode or 'default'}:{plan.start_time.isoformat()}"


def evaluate_plan(plan: AcquisitionPlan, now: datetime) -> DryRunEvaluation:
    if now.tzinfo is None or plan.start_time.tzinfo is None or plan.end_time.tzinfo is None:
        raise ValueError("evaluation times must be timezone-aware")
    identity = plan_identity(plan)
    operation = {
        "source": plan.source,
        "surface_id": plan.surface_id,
        "feed_mode": plan.feed_mode,
        "destination": plan.destination_name,
        "start": plan.start_time.isoformat(),
        "end": plan.end_time.isoformat(),
        "execute": False,
    }
    if plan.surface_id is None:
        state, reason = "blocked", "surface mapping is unresolved"
    elif plan.status in {"unmapped-surface", "error"}:
        state, reason = "blocked", plan.reason or plan.status
    elif now < plan.start_time:
        state, reason = "waiting", "outside acquisition window"
    elif now < plan.end_time:
        state, reason = "active-dry-run", "inside acquisition window"
    else:
        state, reason = "completed-dry-run", "window elapsed"
    return DryRunEvaluation(identity, state, plan, operation, reason)


def evaluate_plans(plans: Iterable[AcquisitionPlan], now: datetime) -> List[DryRunEvaluation]:
    evaluations = [evaluate_plan(plan, now) for plan in plans]
    seen = set()
    result = []
    for evaluation in sorted(evaluations, key=lambda item: item.identity):
        if evaluation.identity not in seen:
            result.append(evaluation)
            seen.add(evaluation.identity)
    return result
