"""Pydantic schemas for findings and evidence.

Follows the ScamTrace AI Phase 1 specifications:
Every rule returns positive, negative, or unknown.
Unknown is the default whenever data is missing, redacted, timed out, or inconclusive.
"""

from datetime import datetime, timezone
from typing import Any, Literal
import uuid
from pydantic import BaseModel, Field, ConfigDict

Outcome = Literal["positive", "negative", "unknown"]
Severity = Literal["info", "low", "medium", "high", "critical"]

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

def new_uuid() -> str:
    return str(uuid.uuid4())

class EvidenceModel(BaseModel):
    id: str = Field(default_factory=new_uuid)
    kind: str = Field(description="Evidence category/format: text, json, html, image, video_frame, dns_record, rdap, etc.")
    source_url: str | None = None
    filename: str | None = None
    storage_path: str | None = None
    sha256: str | None = None
    captured_at: datetime | None = None
    observed_at: datetime = Field(default_factory=utc_now)
    provenance: str | None = Field(default=None, description="Origin provenance, e.g. 'user_supplied', 'browser_active_tab', 'public_dns', 'rdap'")
    content_preview: str | None = None
    raw_data: dict[str, Any] | None = None

    model_config = ConfigDict(from_attributes=True)

class FindingModel(BaseModel):
    rule_id: str = Field(description="Machine-readable rule identifier, e.g. 'lookalike_domain', 'domain_age'")
    outcome: Outcome = Field(default="unknown", description="Evaluation result: positive (risk detected), negative (clean/clear), or unknown")
    severity: Severity = Field(default="low", description="Provisional severity level if positive: info, low, medium, high, critical")
    rationale: str = Field(description="Deterministic explanation of why this outcome was determined")
    evidence_ids: list[str] = Field(default_factory=list, description="IDs of backing Evidence records")
    source: str | None = Field(default=None, description="Target domain, URL, or identifier inspected")
    observed_at: datetime = Field(default_factory=utc_now)
    rule_version: str = Field(default="1.0.0", description="Rule implementation version for provenance")
    limitations: list[str] = Field(default_factory=list, description="Documented limitations, missing data, or caveats")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Structured metrics, e.g. edit distance, days old, etc.")

    model_config = ConfigDict(from_attributes=True)
