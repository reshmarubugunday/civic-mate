"""Government-to-citizen alerts feed (scoped-down version of the section 23
"future module").

Rather than building the full inbound pipeline described in the original
doc (verified inbox, SPF/DKIM/DMARC checks, human review queue), this ships
the minimum that demonstrates the core safety property: unverified senders
are never auto-published. Alerts are seeded server-side against a small
trusted-domain allowlist; anything from an unlisted domain is rejected
before it would ever reach GET /api/alerts.

Production path (not built): replace the seed list with real inbound
ingestion (email or API) plus SPF/DKIM/DMARC verification and a human
review queue for anything that doesn't pass automatically, per the original
section 23 design.
"""
from dataclasses import dataclass

TRUSTED_ALERT_DOMAINS = {"demo.civicmate.local"}


@dataclass(frozen=True)
class Alert:
    sender: str
    subject: str
    body: str
    published_at: str


_SEED_ALERTS = [
    Alert(
        sender="water-supply@demo.civicmate.local",
        subject="Scheduled water shutdown — Ward 4",
        body="Water supply will be interrupted 9am-2pm on 2026-09-05 for pipeline maintenance.",
        published_at="2026-09-01T08:00:00+00:00",
    ),
    Alert(
        sender="roads-highways@demo.civicmate.local",
        subject="Road closure — Main St bridge repair",
        body="Main St bridge closed to traffic 2026-09-04 through 2026-09-10. Use 5th Ave detour.",
        published_at="2026-09-02T10:00:00+00:00",
    ),
    # Example of what gets rejected: an unlisted/unverified sender domain.
    # Left commented to document the check rather than exercised at runtime,
    # since publish_alert() would raise for it.
    # Alert(sender="notices@random-domain.example", subject="...", body="...", published_at="..."),
]


def publish_alert(alert: Alert) -> Alert:
    domain = alert.sender.split("@")[-1].lower()
    if domain not in TRUSTED_ALERT_DOMAINS:
        raise ValueError(f"Sender domain not in trusted directory: {domain}")
    return alert


def list_alerts() -> list[Alert]:
    return [publish_alert(a) for a in _SEED_ALERTS]
