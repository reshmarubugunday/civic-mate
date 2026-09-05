"""Autonomous follow-through: the agent decides on its own, not a human
clicking a button.

Previously "Simulate follow-up" / "Simulate escalation" only fired when a
citizen (or a judge watching a demo) clicked a button — nothing in
CivicMate actually kept working after a complaint was submitted. This
background loop periodically re-evaluates every open complaint and asks
the agent (app.agent.assess_followup_action) whether it needs a follow-up
or escalation, based on elapsed time and priority — the same
Bedrock-preferred / deterministic-fallback pattern as triage, so a Bedrock
outage doesn't mean the agent silently stops following through.

The manual "Simulate" endpoints in app/main.py still exist for direct
control/testing; this loop is what actually satisfies the architecture's
"autonomous follow-through" principle rather than just describing it.
"""
import asyncio
import logging
from datetime import datetime, timezone

from app import config
from app.agent import assess_followup_action
from app.email_sender import send_status_update
from app.models import Status
from app.store import store

logger = logging.getLogger("civicmate.scheduler")

_ACTIONABLE_STATUSES = {Status.SUBMITTED.value, Status.FOLLOWED_UP.value}


def _elapsed_seconds(complaint) -> float:
    updated = datetime.fromisoformat(complaint.updated_at)
    return (datetime.now(timezone.utc) - updated).total_seconds()


def _apply_action(complaint, action: str, reason: str, engine) -> None:
    if action == "follow_up":
        complaint.status = Status.FOLLOWED_UP
        event = "Follow-up sent automatically"
    elif action == "escalate":
        complaint.status = Status.ESCALATED
        event = "Escalated by CivicMate AI"
    else:
        return

    complaint.log(event, detail=f"autonomous decision (engine={engine.value}): {reason}")
    store.put(complaint)
    logger.info("Autonomous %s: %s (%s)", action, complaint.reference_number, reason)

    if complaint.citizen_email:
        send_status_update(complaint.citizen_email, complaint.reference_number, event, reason)


async def run_autonomous_cycle() -> int:
    """Evaluates every open, approved complaint once. Returns how many
    complaints had an action applied — used by tests/manual runs."""
    actioned = 0
    for complaint in store.list():
        if not complaint.approved or complaint.status.value not in _ACTIONABLE_STATUSES:
            continue

        elapsed = _elapsed_seconds(complaint)
        decision = await asyncio.to_thread(
            assess_followup_action, complaint.priority.value, complaint.status.value, elapsed,
        )
        if decision["action"] != "no_action":
            _apply_action(complaint, decision["action"], decision["reason"], decision["engine"])
            actioned += 1
    return actioned


async def scheduler_loop() -> None:
    logger.info(
        "Autonomous follow-through loop starting (interval=%ss, follow_up>=%ss, escalate>=%ss)",
        config.AUTONOMOUS_CHECK_INTERVAL_SECONDS,
        config.FOLLOWUP_THRESHOLD_SECONDS,
        config.ESCALATION_THRESHOLD_SECONDS,
    )
    while True:
        try:
            await run_autonomous_cycle()
        except Exception:  # noqa: BLE001 - the loop must never die from one bad cycle
            logger.exception("Autonomous follow-through cycle failed; will retry next interval")
        await asyncio.sleep(config.AUTONOMOUS_CHECK_INTERVAL_SECONDS)
