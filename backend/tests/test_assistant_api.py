from uuid import uuid4

from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from app.db.models import Document, DocumentChunk, DocumentProcessingStatus, Equipment
from app.db.session import create_session_factory
from app.main import create_app


def test_assistant_api_uses_the_assistant_namespace():
    app = create_app(database_url="sqlite+aiosqlite:///:memory:")

    paths = app.openapi()["paths"]

    assert "/api/v1/assistant/chat" in paths
    assert "/api/v1/assistant/conversations" in paths
    assert "/api/v1/agent/chat" not in paths


def test_assistant_chat_returns_cited_relational_document_source(tmp_path):
    database_file = tmp_path / "assistant-chat.db"
    database_url = "sqlite+aiosqlite:///{}".format(database_file.as_posix())
    model = FakeListChatModel(responses=["先断电，再检查电源接头。[S1]"])
    app = create_app(database_url=database_url, assistant_model=model)

    with TestClient(app) as client:
        async def add_manual():
            async with create_session_factory(app.state.db_engine)() as session:
                equipment = Equipment(equipment_code="TDL5A", name="离心机")
                document = Document(
                    id=str(uuid4()),
                    equipment_code="TDL5A",
                    filename="manual.md",
                    title="离心机维修手册",
                    checksum="a" * 64,
                    source_path="manuals/TDL5A/manual.md",
                    processing_status=DocumentProcessingStatus.READY,
                )
                session.add_all([equipment, document])
                await session.flush()
                session.add(
                    DocumentChunk(
                        id=str(uuid4()),
                        document_id=document.id,
                        checksum=document.checksum,
                        chunk_index=0,
                        content="设备出现故障时先断电，再检查电源接头。",
                        chapter="安全处理",
                        page_start=2,
                        page_end=2,
                        source_path=document.source_path,
                    )
                )
                await session.commit()

        client.portal.call(add_manual)
        login = client.post(
            "/api/v1/auth/login",
            json={"username": "stu", "password": "12345678"},
        )
        response = client.post(
            "/api/v1/assistant/chat",
            json={"query": "设备故障时如何处理？", "equipment_id": "TDL5A"},
            headers={"Authorization": "Bearer " + login.json()["access_token"]},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "completed"
    assert payload["answer"] == "先断电，再检查电源接头。[S1]"
    assert len(payload["sources"]) == 1
    source = payload["sources"][0]
    assert source["id"] == "S1"
    assert source["title"] == "离心机维修手册"
    assert source["filename"] == "manual.md"
    assert source["source_path"] == "manuals/TDL5A/manual.md"
    assert source["chapter"] == "安全处理"
    assert source["page_start"] == source["page_end"] == 2
    assert source["excerpt"] == "设备出现故障时先断电，再检查电源接头。"
