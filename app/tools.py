"""Deterministic civic-issue classification, priority, and routing logic.

Used both as the demo fallback engine and as the tool implementations that
back the Strands agent (app/agent.py), so behavior stays consistent whether
or not Bedrock is reachable.
"""
from typing import Tuple

CRITICAL_ELECTRICAL_KEYWORDS = [
    "live wire", "fallen wire", "sparking transformer", "sparking",
    "exposed live cable", "exposed wire", "fire at transformer",
    "electrical fire", "live cable", "electrocut",
]

CATEGORY_RULES: list[Tuple[str, list[str], str]] = [
    (
        "Stray Animals / Animal Welfare",
        ["stray dog", "stray cattle", "stray animal", "roaming animal",
         "dog bite", "dangerous animal", "stray cow"],
        "Municipal Animal Welfare / Veterinary Department",
    ),
    (
        "Electricity / Power Supply",
        ["power cut", "power failure", "no electricity", "voltage",
         "transformer", "electrical pole", "electrical wire", "power outage",
         "sparking", "live wire", "electrocut"],
        "Electricity Board",
    ),
    (
        "Street Lighting",
        ["streetlight", "street light", "street lamp", "dark road",
         "lamp post not working"],
        "Electrical / Street Lighting Department",
    ),
    (
        "Road Damage",
        ["pothole", "damaged road", "broken road", "road surface",
         "cracked road", "road crack"],
        "Roads / Highways Department",
    ),
    (
        "Garbage Collection",
        ["garbage", "trash", "waste not collected", "litter", "dumping"],
        "Sanitation Department",
    ),
    (
        "Drainage / Sewage",
        ["drainage", "sewage", "sewer", "drain blocked", "overflow"],
        "Drainage / Sewage Department",
    ),
    (
        "Water Leakage",
        ["water leak", "pipe burst", "water pipe", "leaking water"],
        "Water Supply Department",
    ),
    (
        "Fallen Trees",
        ["fallen tree", "tree fell", "tree blocking", "branch fell"],
        "Parks / Forestry Department",
    ),
]

DEFAULT_CATEGORY = "General Public Hazard"
DEFAULT_DEPARTMENT = "General Municipal Services"

ALLOWED_CATEGORIES = {cat for cat, _kw, _dept in CATEGORY_RULES} | {DEFAULT_CATEGORY}
ALLOWED_PRIORITIES = {"Normal", "High", "Critical / Emergency"}
ALLOWED_FOLLOWTHROUGH_ACTIONS = {"no_action", "follow_up", "escalate"}


def classify_issue(description: str) -> dict:
    text = description.lower()
    for category, keywords, department in CATEGORY_RULES:
        if any(k in text for k in keywords):
            return {"category": category, "department": department}
    return {"category": DEFAULT_CATEGORY, "department": DEFAULT_DEPARTMENT}


def is_critical_electrical_hazard(description: str) -> bool:
    text = description.lower()
    return any(k in text for k in CRITICAL_ELECTRICAL_KEYWORDS)


def assess_priority(description: str, category: str) -> str:
    if is_critical_electrical_hazard(description):
        return "Critical / Emergency"

    text = description.lower()
    high_signals = [
        "flood", "flooding", "danger", "dangerous", "hazard", "urgent",
        "accident", "injur", "blocking road", "no water supply",
    ]
    if any(s in text for s in high_signals):
        return "High"
    if category in {"Electricity / Power Supply", "Stray Animals / Animal Welfare"}:
        return "High"
    return "Normal"


def normalize_location(location: str) -> str:
    return " ".join(location.strip().lower().split())


def resolve_department(category: str) -> str:
    for cat, _keywords, department in CATEGORY_RULES:
        if cat == category:
            return department
    return DEFAULT_DEPARTMENT


def decide_next_action(priority: str, status: str, elapsed_seconds: float,
                        followup_threshold: float, escalation_threshold: float) -> dict:
    """Deterministic fallback for autonomous follow-through (app/scheduler.py).

    Critical cases move twice as fast as normal ones — a live wire that's
    been sitting untouched for six hours deserves more urgency than a
    pothole in the same window.
    """
    urgency_factor = 0.5 if priority == "Critical / Emergency" else 1.0

    if status == "Submitted to mock civic service" and elapsed_seconds >= followup_threshold * urgency_factor:
        return {"action": "follow_up", "reason": f"No update {int(elapsed_seconds)}s after submission"}
    if status == "Follow-up sent automatically" and elapsed_seconds >= escalation_threshold * urgency_factor:
        return {"action": "escalate", "reason": f"No resolution {int(elapsed_seconds)}s after follow-up"}
    return {"action": "no_action", "reason": "Within normal response window"}


def build_complaint_text(description: str, location: str, category: str,
                          department: str, priority: str) -> str:
    urgency_note = ""
    if priority == "Critical / Emergency":
        urgency_note = (
            "\n\nTHIS IS A CRITICAL / EMERGENCY REPORT. Immediate attention is "
            "requested due to potential public safety risk."
        )
    return (
        f"Subject: Civic complaint — {category}\n\n"
        f"Location: {location}\n"
        f"Category: {category}\n"
        f"Priority: {priority}\n"
        f"Routed to: {department}\n\n"
        f"Description reported by citizen:\n{description}"
        f"{urgency_note}\n\n"
        "This complaint was prepared by CivicMate AI on behalf of the citizen, "
        "who has reviewed and approved this submission."
    )
