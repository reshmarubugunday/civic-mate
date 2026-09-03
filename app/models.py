import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def new_reference() -> str:
    return f"CM-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"


class Priority(str, Enum):
    NORMAL = "Normal"
    HIGH = "High"
    CRITICAL = "Critical / Emergency"


class Status(str, Enum):
    PREPARED = "Prepared — awaiting citizen approval"
    SUBMITTED = "Submitted to mock civic service"
    FOLLOWED_UP = "Follow-up sent automatically"
    ESCALATED = "Escalated by CivicMate AI"


class Engine(str, Enum):
    BEDROCK = "Strands + Amazon Bedrock"
    DEMO = "Demo fallback (Bedrock unavailable)"


class ActivityEvent(BaseModel):
    timestamp: str = Field(default_factory=now_iso)
    event: str
    detail: Optional[str] = None


class ComplaintCreate(BaseModel):
    description: str
    location: str
    attachment_name: Optional[str] = None
    attachment_url: Optional[str] = None


class ApprovalRequest(BaseModel):
    final_recipient_email: str
    cc_email: Optional[str] = None


class Complaint(BaseModel):
    complaint_id: str = Field(default_factory=new_id)
    reference_number: str = Field(default_factory=new_reference)

    description: str
    location: str
    category: str = "Uncategorized"
    priority: Priority = Priority.NORMAL
    department: str = "General Municipal Services"
    status: Status = Status.PREPARED

    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)

    engine: Engine = Engine.DEMO
    complaint_text: str = ""

    suggested_recipient_email: str = ""
    final_recipient_email: Optional[str] = None
    recipient_verified: bool = False
    recipient_edited: bool = False

    citizen_email: str = ""
    reporters: List[str] = Field(default_factory=list)
    subject: str = ""

    attachment_name: Optional[str] = None
    attachment_url: Optional[str] = None

    approved: bool = False
    activity: List[ActivityEvent] = Field(default_factory=list)

    def log(self, event: str, detail: Optional[str] = None) -> None:
        self.activity.append(ActivityEvent(event=event, detail=detail))
        self.updated_at = now_iso()
