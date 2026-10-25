import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, Integer, DateTime, ForeignKey, Float, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

def uid(): return str(uuid.uuid4())
def now(): return datetime.now(timezone.utc)

class Case(Base):
    __tablename__ = "cases"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    title: Mapped[str] = mapped_column(String(240))
    mode: Mapped[str] = mapped_column(String(30), default="pre_purchase")
    status: Mapped[str] = mapped_column(String(30), default="created")
    store_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    seller_handle: Mapped[str | None] = mapped_column(String(240), nullable=True)
    product_name: Mapped[str | None] = mapped_column(String(240), nullable=True)
    amount_minor_units: Mapped[int | None] = mapped_column(Integer, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
    evidence = relationship("Evidence", cascade="all, delete-orphan", back_populates="case")
    findings = relationship("Finding", cascade="all, delete-orphan", back_populates="case")
    runs = relationship("InvestigationRun", cascade="all, delete-orphan", back_populates="case")

class Evidence(Base):
    __tablename__ = "evidence"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(30))
    filename: Mapped[str] = mapped_column(String(255))
    storage_path: Mapped[str] = mapped_column(String(2048))
    sha256: Mapped[str] = mapped_column(String(64))
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    extraction_status: Mapped[str] = mapped_column(String(30), default="not_started")
    case = relationship("Case", back_populates="evidence")

class Finding(Base):
    __tablename__ = "findings"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"))
    category: Mapped[str] = mapped_column(String(80))
    claim: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="unverified")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    risk_weight: Mapped[int] = mapped_column(Integer, default=0)
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    evidence_id: Mapped[str | None] = mapped_column(ForeignKey("evidence.id"), nullable=True)
    evidence_strength: Mapped[str] = mapped_column(String(20), default="weak")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    case = relationship("Case", back_populates="findings")

class InvestigationRun(Base):
    __tablename__ = "investigation_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(30), default="queued")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    steps_used: Mapped[int] = mapped_column(Integer, default=0)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    case = relationship("Case", back_populates="runs")

class ToolAudit(Base):
    __tablename__ = "tool_audit"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"))
    run_id: Mapped[str] = mapped_column(String(36))
    tool_name: Mapped[str] = mapped_column(String(80))
    input_summary: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    status: Mapped[str] = mapped_column(String(30))
    result_summary: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class Report(Base):
    __tablename__ = "reports"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"))
    version: Mapped[int] = mapped_column(Integer, default=1)
    storage_path: Mapped[str] = mapped_column(String(2048))
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    risk_level: Mapped[str] = mapped_column(String(30))
    evidence_snapshot_hash: Mapped[str] = mapped_column(String(64))


class InspectionRequest(Base):
    __tablename__ = "inspection_requests"
    request_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
