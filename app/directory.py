"""Department contact directory.

This closes the "recipient addresses are just guessed slugs" gap by
separating two concerns that used to be conflated:

  1. Which address does CivicMate suggest for a department?
  2. Has that address been curated/checked by anyone, or auto-generated?

`verified=True` means the entry was deliberately added to this directory
(the analogue of an admin-curated registry) — it does NOT mean the address
has been confirmed to be a real, working government inbox. Per section 10
of the architecture doc, CivicMate must never claim a manually-entered or
auto-guessed government address is verified. Directory entries below use
placeholder demo domains for exactly this reason.

Production path (not built): back this with a real, periodically-audited
registry (e.g. a DynamoDB table with source/audit metadata) maintained by
municipal staff, with `verified` meaning "confirmed deliverable."
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class DirectoryEntry:
    email: str
    verified: bool


# Seed directory: a handful of departments CivicMate "knows about" ahead of
# time, standing in for a curated registry. Anything not listed here falls
# back to an auto-generated, explicitly-unverified address.
_DIRECTORY: dict[str, DirectoryEntry] = {
    "Electrical / Street Lighting Department": DirectoryEntry(
        "streetlighting@demo.civicmate.local", verified=True),
    "Roads / Highways Department": DirectoryEntry(
        "roads-highways@demo.civicmate.local", verified=True),
    "Municipal Animal Welfare / Veterinary Department": DirectoryEntry(
        "animal-welfare@demo.civicmate.local", verified=True),
    "Electricity Board": DirectoryEntry(
        "electricity-board@demo.civicmate.local", verified=True),
    "Sanitation Department": DirectoryEntry(
        "sanitation@demo.civicmate.local", verified=True),
    "Drainage / Sewage Department": DirectoryEntry(
        "drainage-sewage@demo.civicmate.local", verified=True),
    "Water Supply Department": DirectoryEntry(
        "water-supply@demo.civicmate.local", verified=True),
    "Parks / Forestry Department": DirectoryEntry(
        "parks-forestry@demo.civicmate.local", verified=True),
}


def lookup(department: str) -> DirectoryEntry:
    if department in _DIRECTORY:
        return _DIRECTORY[department]
    slug = department.lower().replace(" / ", "-").replace(" ", "-")
    return DirectoryEntry(email=f"{slug}@demo.civicmate.local", verified=False)
