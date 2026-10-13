from datetime import datetime, timezone
from enum import Enum as PythonEnum
from typing import List, Optional
from uuid import uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Enum as SqlEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _uuid() -> str:
    return str(uuid4())


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _enum(enum_type, name: str) -> SqlEnum:
    return SqlEnum(
        enum_type,
        name=name,
        native_enum=False,
        create_constraint=True,
        validate_strings=True,
        values_callable=lambda values: [value.value for value in values],
    )


class UserRole(str, PythonEnum):
    STUDENT = "student"
    TEACHER = "teacher"
    ADMIN = "admin"


class UserStatus(str, PythonEnum):
    ACTIVE = "active"
    DISABLED = "disabled"


class EquipmentStatus(str, PythonEnum):
    AVAILABLE = "available"
    IN_USE = "in_use"
    MAINTENANCE = "maintenance"
    RETIRED = "retired"


class WorkOrderStatus(str, PythonEnum):
    SUBMITTED = "submitted"
    APPROVED = "approved"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class WorkOrderPriority(str, PythonEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class MaintenancePlanStatus(str, PythonEnum):
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class DocumentProcessingStatus(str, PythonEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class ConversationStatus(str, PythonEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class MessageRole(str, PythonEnum):
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class AssistantRunStatus(str, PythonEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    NO_ANSWER = "no_answer"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AssistantToolInvocationStatus(str, PythonEnum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REJECTED = "rejected"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    username: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    email: Mapped[Optional[str]] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    role: Mapped[UserRole] = mapped_column(_enum(UserRole, "user_role"), nullable=False)
    status: Mapped[UserStatus] = mapped_column(
        _enum(UserStatus, "user_status"), nullable=False, default=UserStatus.ACTIVE
    )
    department: Mapped[Optional[str]] = mapped_column(String(120))
    # Seeded development accounts start unassigned and are bound by an administrator.
    college_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("colleges.id", ondelete="RESTRICT")
    )

    college: Mapped[Optional["College"]] = relationship(back_populates="users")
    managed_laboratories: Mapped[List["Laboratory"]] = relationship(
        back_populates="manager_teacher", foreign_keys="Laboratory.manager_teacher_id"
    )

    requested_work_orders: Mapped[List["WorkOrder"]] = relationship(
        back_populates="requester", foreign_keys="WorkOrder.requester_id"
    )
    assigned_work_orders: Mapped[List["WorkOrder"]] = relationship(
        back_populates="assignee", foreign_keys="WorkOrder.assignee_id"
    )
    conversations: Mapped[List["Conversation"]] = relationship(back_populates="user")


class Equipment(TimestampMixin, Base):
    __tablename__ = "equipments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    equipment_code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String(100))
    model: Mapped[Optional[str]] = mapped_column(String(120))
    manufacturer: Mapped[Optional[str]] = mapped_column(String(160))
    serial_number: Mapped[Optional[str]] = mapped_column(String(120), unique=True)
    status: Mapped[EquipmentStatus] = mapped_column(
        _enum(EquipmentStatus, "equipment_status"),
        nullable=False,
        default=EquipmentStatus.AVAILABLE,
    )
    description: Mapped[Optional[str]] = mapped_column(Text)
    # The API requires this relationship; nullable keeps direct ORM fixtures lightweight.
    laboratory_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("laboratories.id", ondelete="RESTRICT")
    )

    laboratory: Mapped[Optional["Laboratory"]] = relationship(back_populates="equipments")

    work_orders: Mapped[List["WorkOrder"]] = relationship(back_populates="equipment")
    maintenance_plans: Mapped[List["MaintenancePlan"]] = relationship(
        back_populates="equipment"
    )
    documents: Mapped[List["Document"]] = relationship(back_populates="equipment")
    conversations: Mapped[List["Conversation"]] = relationship(back_populates="equipment")


class College(Base):
    __tablename__ = "colleges"
    __table_args__ = (UniqueConstraint("name", name="uq_colleges_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(120), nullable=False)

    users: Mapped[List[User]] = relationship(back_populates="college")
    laboratories: Mapped[List["Laboratory"]] = relationship(
        back_populates="college", cascade="save-update, merge"
    )


class Laboratory(Base):
    __tablename__ = "laboratories"
    __table_args__ = (
        UniqueConstraint(
            "college_id", "laboratory_number", name="uq_laboratories_college_number"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    laboratory_number: Mapped[str] = mapped_column(String(64), nullable=False)
    college_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("colleges.id", ondelete="RESTRICT"), nullable=False
    )
    manager_teacher_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )

    college: Mapped[College] = relationship(back_populates="laboratories")
    manager_teacher: Mapped[User] = relationship(
        back_populates="managed_laboratories", foreign_keys=[manager_teacher_id]
    )
    equipments: Mapped[List[Equipment]] = relationship(back_populates="laboratory")


class WorkOrder(TimestampMixin, Base):
    __tablename__ = "work_orders"
    __table_args__ = (
        Index("ix_work_orders_equipment_status", "equipment_id", "status"),
        Index("ix_work_orders_requester_created", "requester_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    equipment_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("equipments.id", ondelete="RESTRICT"), nullable=False
    )
    requester_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    assignee_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[WorkOrderPriority] = mapped_column(
        _enum(WorkOrderPriority, "work_order_priority"),
        nullable=False,
        default=WorkOrderPriority.NORMAL,
    )
    status: Mapped[WorkOrderStatus] = mapped_column(
        _enum(WorkOrderStatus, "work_order_status"),
        nullable=False,
        default=WorkOrderStatus.SUBMITTED,
    )
    resolution: Mapped[Optional[str]] = mapped_column(Text)
    assigned_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    equipment: Mapped[Equipment] = relationship(back_populates="work_orders")
    requester: Mapped[User] = relationship(
        back_populates="requested_work_orders", foreign_keys=[requester_id]
    )
    assignee: Mapped[Optional[User]] = relationship(
        back_populates="assigned_work_orders", foreign_keys=[assignee_id]
    )


class MaintenancePlan(TimestampMixin, Base):
    __tablename__ = "maintenance_plans"
    __table_args__ = (
        Index("ix_maintenance_plans_status_due", "status", "due_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    equipment_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("equipments.id", ondelete="RESTRICT"), nullable=False
    )
    created_by_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    assignee_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    details: Mapped[Optional[str]] = mapped_column(Text)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[MaintenancePlanStatus] = mapped_column(
        _enum(MaintenancePlanStatus, "maintenance_plan_status"),
        nullable=False,
        default=MaintenancePlanStatus.PLANNED,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    equipment: Mapped[Equipment] = relationship(back_populates="maintenance_plans")
    created_by: Mapped[User] = relationship(foreign_keys=[created_by_id])
    assignee: Mapped[Optional[User]] = relationship(foreign_keys=[assignee_id])


class Document(TimestampMixin, Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    equipment_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("equipments.id", ondelete="SET NULL")
    )
    equipment_code: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    uploaded_by_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL")
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    source_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    processing_status: Mapped[DocumentProcessingStatus] = mapped_column(
        _enum(DocumentProcessingStatus, "document_processing_status"),
        nullable=False,
        default=DocumentProcessingStatus.PENDING,
    )
    processing_error: Mapped[Optional[str]] = mapped_column(Text)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    equipment: Mapped[Optional[Equipment]] = relationship(back_populates="documents")
    chunks: Mapped[List["DocumentChunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", passive_deletes=True
    )

class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint(
            "document_id", "checksum", "chunk_index", name="uq_document_chunk_version_index"
        ),
        CheckConstraint("chunk_index >= 0", name="ck_document_chunk_index_nonnegative"),
        CheckConstraint(
            "page_start IS NULL OR page_start > 0", name="ck_document_chunk_page_start_positive"
        ),
        CheckConstraint(
            "page_end IS NULL OR page_end > 0", name="ck_document_chunk_page_end_positive"
        ),
        CheckConstraint(
            "page_start IS NULL OR page_end IS NULL OR page_end >= page_start",
            name="ck_document_chunk_page_range_valid",
        ),
        Index("ix_document_chunks_document_index", "document_id", "chunk_index"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    document_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    chapter: Mapped[Optional[str]] = mapped_column(String(500))
    page_start: Mapped[Optional[int]] = mapped_column(Integer)
    page_end: Mapped[Optional[int]] = mapped_column(Integer)
    source_path: Mapped[str] = mapped_column(String(1024), nullable=False)

    document: Mapped[Document] = relationship(back_populates="chunks")


class Conversation(TimestampMixin, Base):
    __tablename__ = "conversations"
    __table_args__ = (
        Index("ix_conversations_user_updated", "user_id", "updated_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    equipment_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("equipments.id", ondelete="SET NULL")
    )
    title: Mapped[Optional[str]] = mapped_column(String(255))
    summary: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[ConversationStatus] = mapped_column(
        _enum(ConversationStatus, "conversation_status"),
        nullable=False,
        default=ConversationStatus.ACTIVE,
    )

    user: Mapped[User] = relationship(back_populates="conversations")
    equipment: Mapped[Optional[Equipment]] = relationship(back_populates="conversations")
    messages: Mapped[List["ConversationMessage"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ConversationMessage.sequence",
    )
    assistant_runs: Mapped[List["AssistantRun"]] = relationship(back_populates="conversation")


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"
    __table_args__ = (
        UniqueConstraint("conversation_id", "sequence", name="uq_conversation_message_sequence"),
        CheckConstraint("sequence >= 0", name="ck_conversation_message_sequence_nonnegative"),
        Index("ix_conversation_messages_created", "conversation_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    conversation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[MessageRole] = mapped_column(_enum(MessageRole, "message_role"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )

    conversation: Mapped[Conversation] = relationship(back_populates="messages")


class AssistantRun(Base):
    __tablename__ = "assistant_runs"
    __table_args__ = (
        UniqueConstraint("user_id", "idempotency_key", name="uq_assistant_run_user_idempotency"),
        Index("ix_assistant_runs_conversation_started", "conversation_id", "started_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    conversation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(128))
    user_query: Mapped[str] = mapped_column(Text, nullable=False)
    intent: Mapped[Optional[str]] = mapped_column(String(100))
    status: Mapped[AssistantRunStatus] = mapped_column(
        _enum(AssistantRunStatus, "assistant_run_status"),
        nullable=False,
        default=AssistantRunStatus.RUNNING,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    conversation: Mapped[Conversation] = relationship(back_populates="assistant_runs")
    events: Mapped[List["AssistantEvent"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", passive_deletes=True
    )
    assistant_tool_invocations: Mapped[List["AssistantToolInvocation"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", passive_deletes=True
    )


class AssistantEvent(Base):
    __tablename__ = "assistant_events"
    __table_args__ = (
        UniqueConstraint("run_id", "sequence", name="uq_assistant_event_sequence"),
        CheckConstraint("sequence >= 0", name="ck_assistant_event_sequence_nonnegative"),
        Index("ix_assistant_events_run_created", "run_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("assistant_runs.id", ondelete="CASCADE"), nullable=False
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    node_name: Mapped[Optional[str]] = mapped_column(String(100))
    payload_json: Mapped[Optional[dict]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )

    run: Mapped[AssistantRun] = relationship(back_populates="events")


class AssistantToolInvocation(Base):
    __tablename__ = "assistant_tool_invocations"
    __table_args__ = (Index("ix_assistant_tool_invocations_run_status", "run_id", "status"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("assistant_runs.id", ondelete="CASCADE"), nullable=False
    )
    tool_name: Mapped[str] = mapped_column(String(120), nullable=False)
    arguments_json: Mapped[Optional[dict]] = mapped_column(JSON)
    result_json: Mapped[Optional[dict]] = mapped_column(JSON)
    status: Mapped[AssistantToolInvocationStatus] = mapped_column(
        _enum(AssistantToolInvocationStatus, "assistant_tool_invocation_status"),
        nullable=False,
        default=AssistantToolInvocationStatus.PENDING,
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    run: Mapped[AssistantRun] = relationship(back_populates="assistant_tool_invocations")
