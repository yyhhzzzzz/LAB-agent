import asyncio
from uuid import uuid4

import pytest
from sqlalchemy import func, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.db.models import (
    AssistantEvent,
    AssistantRun,
    AssistantRunStatus,
    Conversation,
    ConversationMessage,
    Document,
    DocumentChunk,
    Equipment,
    MaintenancePlan,
    MessageRole,
    AssistantToolInvocation,
    User,
    UserRole,
    WorkOrder,
)
from app.db.session import create_database_engine, create_session_factory, initialize_database


def test_config_resolves_relative_sqlite_url_to_project_root(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///data/test-lab-device-assistant.db")

    settings = Settings.from_env()

    assert settings.database_url.endswith("/data/test-lab-device-assistant.db")
    assert settings.database_url.startswith("sqlite+aiosqlite:///")


def test_application_startup_creates_the_configured_database(tmp_path):
    database_file = tmp_path / "startup" / "lab-device-assistant.db"
    database_url = "sqlite+aiosqlite:///{}".format(database_file.as_posix())
    app = create_app(database_url=database_url)

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert database_file.is_file()
    assert database_file.stat().st_size > 0


def test_async_sqlite_schema_persists_lab_device_assistant_data(tmp_path):
    async def exercise_database():
        database_file = tmp_path / "lab-device-assistant.db"
        engine = create_database_engine(
            "sqlite+aiosqlite:///{}".format(database_file.as_posix())
        )
        try:
            await initialize_database(engine)
            async with engine.connect() as connection:
                table_names = await connection.run_sync(
                    lambda sync_connection: inspect(sync_connection).get_table_names()
                )
                foreign_keys_result = await connection.exec_driver_sql("PRAGMA foreign_keys")
                foreign_keys_enabled = foreign_keys_result.scalar_one()

            assert {
                "users",
                "colleges",
                "laboratories",
                "equipments",
                "work_orders",
                "maintenance_plans",
                "documents",
                "document_chunks",
                "conversations",
                "conversation_messages",
                "assistant_runs",
                "assistant_events",
                "assistant_tool_invocations",
            }.issubset(table_names)
            assert not {
                "agent_runs",
                "agent_events",
                "tool_invocations",
            }.intersection(table_names)
            assert foreign_keys_enabled == 1

            session_factory = create_session_factory(engine)
            async with session_factory() as session:
                student = User(
                    username="student-01",
                    password_hash="argon2$hash",
                    display_name="Student One",
                    role=UserRole.STUDENT,
                )
                teacher = User(
                    username="teacher-01",
                    password_hash="argon2$hash",
                    display_name="Teacher One",
                    role=UserRole.TEACHER,
                )
                admin = User(
                    username="admin-01",
                    password_hash="argon2$hash",
                    display_name="Admin One",
                    role=UserRole.ADMIN,
                )
                equipment = Equipment(
                    equipment_code="CENT-01",
                    name="Centrifuge",
                )
                session.add_all([student, teacher, admin, equipment])
                await session.flush()

                work_order = WorkOrder(
                    equipment_id=equipment.id,
                    requester_id=student.id,
                    assignee_id=teacher.id,
                    title="Unusual vibration",
                    description="The centrifuge vibrates during operation.",
                )
                maintenance_plan = MaintenancePlan(
                    equipment_id=equipment.id,
                    created_by_id=teacher.id,
                    title="Quarterly inspection",
                    due_at=student.created_at,
                )
                document = Document(
                    id=str(uuid4()),
                    equipment_id=equipment.id,
                    filename="centrifuge.md",
                    title="Centrifuge manual",
                    checksum="a" * 64,
                    source_path="manuals/centrifuge.md",
                )
                conversation = Conversation(
                    user_id=student.id,
                    equipment_id=equipment.id,
                    title="Vibration question",
                )
                session.add_all([work_order, maintenance_plan, document, conversation])
                await session.flush()

                session.add_all(
                    [
                        DocumentChunk(
                            id=str(uuid4()),
                            document_id=document.id,
                            checksum=document.checksum,
                            chunk_index=0,
                            content="Inspect the rotor and check the equipment balance.",
                            chapter="Troubleshooting",
                            page_start=2,
                            page_end=2,
                            source_path=document.source_path,
                        ),
                        ConversationMessage(
                            conversation_id=conversation.id,
                            sequence=0,
                            role=MessageRole.USER,
                            content="Why is the centrifuge vibrating?",
                        ),
                    ]
                )
                assistant_run = AssistantRun(
                    conversation_id=conversation.id,
                    user_id=student.id,
                    user_query="Why is the centrifuge vibrating?",
                    status=AssistantRunStatus.COMPLETED,
                )
                session.add(assistant_run)
                await session.flush()
                session.add_all(
                    [
                        AssistantEvent(
                            run_id=assistant_run.id,
                            sequence=0,
                            event_type="documents.loaded",
                            payload_json={"citation_count": 1},
                        ),
                        AssistantToolInvocation(
                            run_id=assistant_run.id,
                            tool_name="read_manual_documents",
                            arguments_json={"equipment_id": equipment.equipment_code},
                            result_json={"matches": 1},
                        ),
                    ]
                )
                await session.commit()

                saved_order = await session.scalar(
                    select(WorkOrder)
                    .options(
                        selectinload(WorkOrder.requester),
                        selectinload(WorkOrder.assignee),
                    )
                    .where(WorkOrder.id == work_order.id)
                )
                assert saved_order is not None
                assert saved_order.requester.role is UserRole.STUDENT
                assert saved_order.assignee.role is UserRole.TEACHER
                message_count = await session.scalar(
                    select(func.count()).select_from(ConversationMessage)
                )
                event_count = await session.scalar(select(func.count()).select_from(AssistantEvent))
                invocation_count = await session.scalar(
                    select(func.count()).select_from(AssistantToolInvocation)
                )
                assert message_count == event_count == invocation_count == 1
        finally:
            await engine.dispose()

    asyncio.run(exercise_database())


def test_usernames_are_unique_in_the_database(tmp_path):
    async def exercise_constraint():
        database_file = tmp_path / "unique-users.db"
        engine = create_database_engine(
            "sqlite+aiosqlite:///{}".format(database_file.as_posix())
        )
        try:
            await initialize_database(engine)
            session_factory = create_session_factory(engine)
            async with session_factory() as session:
                session.add_all(
                    [
                        User(
                            username="same-login",
                            password_hash="hash-one",
                            display_name="One",
                            role=UserRole.STUDENT,
                        ),
                        User(
                            username="same-login",
                            password_hash="hash-two",
                            display_name="Two",
                            role=UserRole.ADMIN,
                        ),
                    ]
                )
                with pytest.raises(IntegrityError):
                    await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(exercise_constraint())
