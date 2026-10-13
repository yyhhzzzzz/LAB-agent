from datetime import datetime, timedelta, timezone
from typing import ClassVar
from uuid import uuid4

from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from sqlalchemy import select

from app.db.models import (
    Document,
    DocumentChunk,
    DocumentProcessingStatus,
    Conversation,
    ConversationStatus,
    Equipment,
    User,
    UserRole,
    WorkOrder,
    WorkOrderStatus,
)
from app.db.session import create_session_factory
from app.main import create_app


class RecordingChatModel(FakeListChatModel):
    seen_messages: ClassVar[list] = []

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.seen_messages.append(messages)
        return super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)


def login(client, username="stu"):
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "12345678"},
    )
    assert response.status_code == 200
    return {"Authorization": "Bearer " + response.json()["access_token"]}


def test_completed_work_order_is_used_before_document_read(tmp_path):
    database_url = "sqlite+aiosqlite:///{}".format((tmp_path / "work-order-first.db").as_posix())
    model = RecordingChatModel(
        responses=[
            '{"relevant_source_ids":["W1"]}',
            "之前的维修记录表明应重新安装转子并做平衡检查。[W1]",
        ]
    )
    app = create_app(database_url=database_url, assistant_model=model)

    with TestClient(app) as client:
        headers = login(client)

        async def seed_history_and_manual():
            async with create_session_factory(app.state.db_engine)() as session:
                equipment = Equipment(equipment_code="TDL5A", name="离心机")
                requester = await session.scalar(select(User).where(User.username == "stu"))
                document = Document(
                    id=str(uuid4()),
                    equipment_code="TDL5A",
                    filename="manual.md",
                    title="不应读取的文档",
                    checksum="b" * 64,
                    source_path="manuals/fallback.md",
                    processing_status=DocumentProcessingStatus.READY,
                )
                session.add_all([equipment, document])
                await session.flush()
                session.add_all(
                    [
                        WorkOrder(
                            equipment_id=equipment.id,
                            requester_id=requester.id,
                            title="运行中振动",
                            description="运行时转子振动且设备报警。",
                            status=WorkOrderStatus.COMPLETED,
                            resolution="重新安装转子并做平衡检查。",
                        ),
                        DocumentChunk(
                            id=str(uuid4()),
                            document_id=document.id,
                            checksum=document.checksum,
                            chunk_index=0,
                            content="DOCUMENT-TOOL-SHOULD-NOT-RUN",
                            source_path=document.source_path,
                        ),
                    ]
                )
                await session.commit()

        client.portal.call(seed_history_and_manual)
        response = client.post(
            "/api/v1/assistant/chat",
            headers=headers,
            json={"query": "运行中振动如何处理？", "equipment_id": "TDL5A"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "completed"
    assert payload["answer"].endswith("[W1]")
    assert payload["sources"][0]["type"] == "work_order"
    assert payload["sources"][0]["title"] == "运行中振动"
    model_input = "\n".join(str(message.content) for message in model.seen_messages[-1])
    assert "W1" in model_input
    assert "重新安装转子并做平衡检查" in model_input
    assert "DOCUMENT-TOOL-SHOULD-NOT-RUN" not in model_input


def test_irrelevant_work_order_falls_back_to_document_reading(tmp_path):
    database_url = "sqlite+aiosqlite:///{}".format((tmp_path / "work-order-fallback.db").as_posix())
    model = RecordingChatModel(
        responses=[
            '{"relevant_source_ids":[]}',
            "手册建议先检查转子是否安装平稳。[S1]",
        ]
    )
    app = create_app(database_url=database_url, assistant_model=model)

    with TestClient(app) as client:
        headers = login(client)

        async def seed_history_and_manual():
            async with create_session_factory(app.state.db_engine)() as session:
                equipment = Equipment(equipment_code="TDL5A", name="离心机")
                requester = await session.scalar(select(User).where(User.username == "stu"))
                document = Document(
                    id=str(uuid4()),
                    equipment_code="TDL5A",
                    filename="manual.md",
                    title="离心机手册",
                    checksum="d" * 64,
                    source_path="manuals/tdl5a.md",
                    processing_status=DocumentProcessingStatus.READY,
                )
                session.add_all([equipment, document])
                await session.flush()
                session.add_all(
                    [
                        WorkOrder(
                            equipment_id=equipment.id,
                            requester_id=requester.id,
                            title="控制面板故障",
                            description="控制面板无法启动。",
                            status=WorkOrderStatus.COMPLETED,
                            resolution="更换控制面板。",
                        ),
                        DocumentChunk(
                            id=str(uuid4()),
                            document_id=document.id,
                            checksum=document.checksum,
                            chunk_index=0,
                            content="异常振动时先检查转子安装和平衡状态。",
                            chapter="异常振动",
                            source_path=document.source_path,
                        ),
                    ]
                )
                await session.commit()

        client.portal.call(seed_history_and_manual)
        response = client.post(
            "/api/v1/assistant/chat",
            headers=headers,
            json={"query": "离心机运行时异常振动怎么办？", "equipment_id": "TDL5A"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["sources"][0]["type"] == "document"
    assert payload["sources"][0]["title"] == "离心机手册"
    assert "异常振动时先检查转子安装和平衡状态" in str(model.seen_messages[-1])


def test_conversation_memory_persists_and_is_reused_by_the_assistant(tmp_path):
    database_url = "sqlite+aiosqlite:///{}".format((tmp_path / "conversation.db").as_posix())
    model = RecordingChatModel(responses=["先检查设备供电。[S1]", "然后再检查电源接头。[S1]"])
    app = create_app(database_url=database_url, assistant_model=model)

    with TestClient(app) as client:
        headers = login(client)

        async def seed_manual():
            async with create_session_factory(app.state.db_engine)() as session:
                document = Document(
                    id=str(uuid4()),
                    equipment_code="TDL5A",
                    filename="manual.md",
                    title="离心机手册",
                    checksum="c" * 64,
                    source_path="manuals/tdl5a.md",
                    processing_status=DocumentProcessingStatus.READY,
                )
                session.add(document)
                await session.flush()
                session.add(
                    DocumentChunk(
                        id=str(uuid4()),
                        document_id=document.id,
                        checksum=document.checksum,
                        chunk_index=0,
                        content="第一步检查设备供电，第二步检查电源接头。",
                        chapter="故障检查",
                        source_path=document.source_path,
                    )
                )
                await session.commit()

        client.portal.call(seed_manual)
        first = client.post(
            "/api/v1/assistant/chat",
            headers=headers,
            json={"query": "设备故障先做什么？", "equipment_id": "TDL5A"},
        )
        conversation_id = first.json()["conversation_id"]
        second = client.post(
            "/api/v1/assistant/chat",
            headers=headers,
            json={
                "query": "然后呢？",
                "equipment_id": "TDL5A",
                "conversation_id": conversation_id,
            },
        )
        restored = client.get(
            "/api/v1/assistant/conversations/{}".format(conversation_id),
            headers=headers,
        )

    assert first.status_code == second.status_code == restored.status_code == 200
    assert second.json()["conversation_id"] == conversation_id
    second_model_input = "\n".join(str(message.content) for message in model.seen_messages[-1])
    assert "设备故障先做什么？" in second_model_input
    assert "先检查设备供电。[S1]" in second_model_input
    assert [message["role"] for message in restored.json()["messages"]] == [
        "user",
        "assistant",
        "user",
        "assistant",
    ]
    assert restored.json()["messages"][1]["sources"][0]["id"] == "S1"
    assert restored.json()["equipment_selector"] == "TDL5A"


def test_assistant_chat_requires_authentication_and_conversations_are_user_scoped(tmp_path):
    app = create_app(
        database_url="sqlite+aiosqlite:///{}".format((tmp_path / "auth-scope.db").as_posix()),
        assistant_model=RecordingChatModel(responses=["无关回答"]),
    )

    with TestClient(app) as client:
        unauthenticated = client.post(
            "/api/v1/assistant/chat",
            json={"query": "问题"},
        )
        student_headers = login(client, "stu")
        created = client.post(
            "/api/v1/assistant/chat",
            headers=student_headers,
            json={"query": "问题", "equipment_id": "TDL5A"},
        )
        scope_mismatch = client.post(
            "/api/v1/assistant/chat",
            headers=student_headers,
            json={
                "query": "另一个设备的问题",
                "equipment_id": "Hitachi",
                "conversation_id": created.json()["conversation_id"],
            },
        )
        teacher_headers = login(client, "tec")
        foreign_read = client.get(
            "/api/v1/assistant/conversations/{}".format(created.json()["conversation_id"]),
            headers=teacher_headers,
        )

    assert unauthenticated.status_code == 401
    assert created.status_code == 200
    assert scope_mismatch.status_code == 409
    assert foreign_read.status_code == 404


def test_conversation_list_is_authenticated_user_scoped_and_newest_first(tmp_path):
    database_url = "sqlite+aiosqlite:///{}".format(
        (tmp_path / "conversation-list.db").as_posix()
    )
    app = create_app(database_url=database_url, assistant_model=RecordingChatModel(responses=[]))

    with TestClient(app) as client:
        student_headers = login(client)
        teacher_headers = login(client, "tec")

        async def seed_conversations():
            async with create_session_factory(app.state.db_engine)() as session:
                student = await session.scalar(select(User).where(User.username == "stu"))
                teacher = await session.scalar(select(User).where(User.username == "tec"))
                base_time = datetime(2025, 1, 1, tzinfo=timezone.utc)
                session.add_all(
                    [
                        Conversation(
                            id=str(uuid4()),
                            user_id=student.id,
                            title="较早的问题",
                            status=ConversationStatus.ACTIVE,
                            created_at=base_time,
                            updated_at=base_time,
                        ),
                        Conversation(
                            id=str(uuid4()),
                            user_id=student.id,
                            title="最近的问题",
                            status=ConversationStatus.ARCHIVED,
                            created_at=base_time + timedelta(minutes=1),
                            updated_at=base_time + timedelta(minutes=1),
                        ),
                        Conversation(
                            id=str(uuid4()),
                            user_id=teacher.id,
                            title="教师的问题",
                            status=ConversationStatus.ACTIVE,
                            created_at=base_time + timedelta(minutes=2),
                            updated_at=base_time + timedelta(minutes=2),
                        ),
                    ]
                )
                await session.commit()

        client.portal.call(seed_conversations)
        unauthenticated = client.get("/api/v1/assistant/conversations")
        student_list = client.get(
            "/api/v1/assistant/conversations",
            headers=student_headers,
        )
        teacher_list = client.get(
            "/api/v1/assistant/conversations",
            headers=teacher_headers,
        )

    assert unauthenticated.status_code == 401
    assert student_list.status_code == 200
    assert teacher_list.status_code == 200
    conversations = student_list.json()
    assert [item["title"] for item in conversations] == ["最近的问题", "较早的问题"]
    assert all(set(item) == {"id", "title", "updated_at", "equipment_id", "status"} for item in conversations)
    assert conversations[0]["status"] == "archived"
    assert [item["title"] for item in teacher_list.json()] == ["教师的问题"]
