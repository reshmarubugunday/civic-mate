import logging

from fastapi import Depends, FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import config, magic_link
from app.agent import run_triage
from app.alerts import list_alerts
from app.auth import issue_token, require_citizen
from app.dedup import find_duplicate
from app.email_sender import send_magic_link
from app.evidence import evidence_store
from app.models import ApprovalRequest, Complaint, ComplaintCreate, Status
from app.store import store

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="CivicMate AI")
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def index():
    return FileResponse("static/index.html")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "store": type(store).__name__,
        "evidence_store": type(evidence_store).__name__,
    }


@app.post("/api/magic-link")
def request_magic_link(payload: dict):
    """Start citizen sign-in: mail a one-time link to the given address.

    A session token (see app/auth.py) is only issued once that link is
    clicked (GET /api/magic-link/verify) — proving mailbox ownership,
    closing the earlier gap where any claimed email got a token outright.
    """
    email = (payload.get("email") or "").strip().lower()
    if not email or "@" not in email:
        raise HTTPException(400, "Valid email required")
    token = magic_link.create_link_token(email)
    link_url = f"{config.APP_BASE_URL}/?token={token}"
    sent = send_magic_link(email, link_url)
    return {
        "sent": sent,
        "message": (
            "Check your email for a sign-in link."
            if sent
            else "Email delivery isn't configured in this environment — check server logs for the link."
        ),
    }


@app.get("/api/magic-link/verify")
def verify_magic_link(token: str):
    email = magic_link.consume_link_token(token)
    if not email:
        raise HTTPException(400, "This link is invalid or has expired. Request a new one.")
    return {"citizen_email": email, "token": issue_token(email)}


def _owns(complaint: Complaint, citizen_email: str) -> bool:
    return citizen_email == complaint.citizen_email or citizen_email in complaint.reporters


@app.post("/api/uploads")
async def upload_evidence(file: UploadFile, citizen_email: str = Depends(require_citizen)):
    if file.content_type not in config.ALLOWED_UPLOAD_TYPES:
        raise HTTPException(400, f"Unsupported file type: {file.content_type}")
    content = await file.read()
    if len(content) > config.MAX_UPLOAD_BYTES:
        raise HTTPException(400, "File exceeds 5 MB limit")
    url = evidence_store.save(file.filename, content)
    return {"attachment_name": file.filename, "attachment_url": url}


@app.post("/api/complaints", response_model=Complaint)
def create_complaint(payload: ComplaintCreate, citizen_email: str = Depends(require_citizen)):
    triage = run_triage(payload.description, payload.location)

    duplicate = find_duplicate(store.list(), triage["category"], payload.location)
    if duplicate and not _owns(duplicate, citizen_email):
        duplicate.reporters.append(citizen_email)
        duplicate.log("Duplicate report merged", detail=f"reporter={citizen_email}")
        store.put(duplicate)
        return duplicate

    complaint = Complaint(
        description=payload.description,
        location=payload.location,
        citizen_email=citizen_email,
        attachment_name=payload.attachment_name,
        attachment_url=payload.attachment_url,
        category=triage["category"],
        department=triage["department"],
        priority=triage["priority"],
        complaint_text=triage["complaint_text"],
        suggested_recipient_email=triage["suggested_recipient_email"],
        recipient_verified=triage["recipient_verified"],
        engine=triage["engine"],
        subject=f"Civic complaint — {triage['category']}",
    )
    complaint.log("Complaint created", detail=f"engine={complaint.engine.value}")
    if complaint.attachment_url:
        complaint.log("Attachment prepared", detail=complaint.attachment_name)

    store.put(complaint)
    return complaint


@app.get("/api/complaints", response_model=list[Complaint])
def list_complaints(citizen_email: str = Depends(require_citizen)):
    return [c for c in store.list() if _owns(c, citizen_email)]


@app.get("/api/complaints/{complaint_id}", response_model=Complaint)
def get_complaint(complaint_id: str, citizen_email: str = Depends(require_citizen)):
    complaint = store.get(complaint_id)
    if not complaint or not _owns(complaint, citizen_email):
        raise HTTPException(404, "Complaint not found")
    return complaint


@app.post("/api/complaints/{complaint_id}/approve", response_model=Complaint)
def approve_complaint(complaint_id: str, approval: ApprovalRequest, citizen_email: str = Depends(require_citizen)):
    complaint = store.get(complaint_id)
    if not complaint or not _owns(complaint, citizen_email):
        raise HTTPException(404, "Complaint not found")
    if complaint.approved:
        raise HTTPException(409, "Complaint has already been approved/submitted")

    edited = approval.final_recipient_email != complaint.suggested_recipient_email
    complaint.recipient_edited = edited
    complaint.final_recipient_email = approval.final_recipient_email
    if edited:
        complaint.recipient_verified = False  # citizen-typed address, not directory-checked
    complaint.approved = True
    complaint.status = Status.SUBMITTED
    complaint.log(
        "Citizen approval",
        detail=f"to={approval.final_recipient_email}, cc={approval.cc_email or complaint.citizen_email}",
    )
    complaint.log("Submission", detail=f"reference={complaint.reference_number}")

    store.put(complaint)
    return complaint


@app.post("/api/complaints/{complaint_id}/simulate-followup", response_model=Complaint)
def simulate_followup(complaint_id: str, citizen_email: str = Depends(require_citizen)):
    complaint = store.get(complaint_id)
    if not complaint or not _owns(complaint, citizen_email):
        raise HTTPException(404, "Complaint not found")
    if not complaint.approved:
        raise HTTPException(409, "Complaint must be approved before follow-up")

    complaint.status = Status.FOLLOWED_UP
    complaint.log("Follow-up")
    store.put(complaint)
    return complaint


@app.post("/api/complaints/{complaint_id}/simulate-escalation", response_model=Complaint)
def simulate_escalation(complaint_id: str, citizen_email: str = Depends(require_citizen)):
    complaint = store.get(complaint_id)
    if not complaint or not _owns(complaint, citizen_email):
        raise HTTPException(404, "Complaint not found")
    if not complaint.approved:
        raise HTTPException(409, "Complaint must be approved before escalation")

    complaint.status = Status.ESCALATED
    complaint.log("Escalation")
    store.put(complaint)
    return complaint


@app.get("/api/alerts")
def get_alerts():
    return [a.__dict__ for a in list_alerts()]
