from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from sqlalchemy import func, select

from app.db.models import Document, DocumentChunk, Equipment
from app.db.session import create_session_factory
from app.main import create_app


def _login_headers(client, username="tec"):
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "12345678"},
    )
    assert response.status_code == 200
    return {"Authorization": "Bearer " + response.json()["access_token"]}


def test_document_upload_persists_chunks_and_is_idempotent(tmp_path, monkeypatch):
    database_url = "sqlite+aiosqlite:///{}".format((tmp_path / "lab-device-assistant.db").as_posix())
    monkeypatch.setenv("DOCUMENT_STORAGE_PATH", str(tmp_path / "documents"))
    app = create_app(
        database_url=database_url,
        assistant_model=FakeListChatModel(responses=["断开电源后检查转子。[S1]"]),
    )

    with TestClient(app) as client:
        teacher_headers = _login_headers(client)
        student_headers = _login_headers(client, "stu")

        async def seed_equipment():
            async with create_session_factory(app.state.db_engine)() as session:
                session.add(Equipment(equipment_code="TDL5A", name="离心机"))
                await session.commit()

        client.portal.call(seed_equipment)
        content = b"# Safety\nDisconnect power before inspecting the rotor.\n\n# Check\nInspect the rotor."
        first = client.post(
            "/api/v1/documents",
            files={"file": ("../centrifuge.md", content, "text/markdown")},
            data={"equipment_code": "TDL5A", "title": "离心机手册"},
            headers=teacher_headers,
        )
        second = client.post(
            "/api/v1/documents",
            files={"file": ("centrifuge.md", content, "text/markdown")},
            data={"equipment_code": "TDL5A"},
            headers=teacher_headers,
        )
        student_upload = client.post(
            "/api/v1/documents",
            files={"file": ("student-upload.md", content, "text/markdown")},
            headers=student_headers,
        )
        login = client.post(
            "/api/v1/auth/login",
            json={"username": "stu", "password": "12345678"},
        )
        answer = client.post(
            "/api/v1/assistant/chat",
            json={"query": "如何检查转子？", "equipment_id": "TDL5A"},
            headers={"Authorization": "Bearer " + login.json()["access_token"]},
        )

        async def read_records():
            async with create_session_factory(app.state.db_engine)() as session:
                document = await session.get(Document, first.json()["id"])
                count = await session.scalar(
                    select(func.count())
                    .select_from(DocumentChunk)
                    .where(DocumentChunk.document_id == first.json()["id"])
                )
                return document, count

        document, count = client.portal.call(read_records)

    assert first.status_code == second.status_code == 201
    assert student_upload.status_code == 403
    first_body = first.json()
    second_body = second.json()
    assert first_body["status"] == "ready"
    assert first_body["chunk_count"] == 2
    assert first_body["duplicate"] is False
    assert second_body["duplicate"] is True
    assert second_body["id"] == first_body["id"]
    assert (tmp_path / "documents" / first_body["id"] / "centrifuge.md").is_file()

    assert answer.status_code == 200
    assert answer.json()["answer"] == "断开电源后检查转子。[S1]"
    assert answer.json()["sources"][0]["title"] == "离心机手册"

    assert document is not None
    assert document.equipment_code == "TDL5A"
    assert count == 2


def test_document_upload_validates_equipment_and_file_type(tmp_path, monkeypatch):
    monkeypatch.setenv("DOCUMENT_STORAGE_PATH", str(tmp_path / "documents"))
    monkeypatch.setenv("DOCUMENT_UPLOAD_MAX_BYTES", "8")
    app = create_app(
        database_url="sqlite+aiosqlite:///{}".format((tmp_path / "lab-device-assistant.db").as_posix())
    )

    with TestClient(app) as client:
        teacher_headers = _login_headers(client)
        unknown_equipment = client.post(
            "/api/v1/documents",
            files={"file": ("manual.md", b"# Manual\nText", "text/markdown")},
            data={"equipment_code": "MISSING"},
            headers=teacher_headers,
        )
        unsupported = client.post(
            "/api/v1/documents",
            files={"file": ("manual.zip", b"archive", "application/zip")},
            headers=teacher_headers,
        )
        oversized = client.post(
            "/api/v1/documents",
            files={"file": ("manual.txt", b"too many bytes", "text/plain")},
            headers=teacher_headers,
        )

    assert unknown_equipment.status_code == 404
    assert unsupported.status_code == 415
    assert oversized.status_code == 413


def test_document_upload_requires_teacher_or_admin(tmp_path):
    app = create_app(
        database_url="sqlite+aiosqlite:///{}".format((tmp_path / "document-permissions.db").as_posix())
    )

    with TestClient(app) as client:
        file = {"file": ("manual.md", b"# Manual\nText", "text/markdown")}
        unauthenticated = client.post("/api/v1/documents", files=file)
        student_upload = client.post(
            "/api/v1/documents",
            files=file,
            headers=_login_headers(client, "stu"),
        )
        admin_upload = client.post(
            "/api/v1/documents",
            files=file,
            headers=_login_headers(client, "admin"),
        )

    assert unauthenticated.status_code == 401
    assert student_upload.status_code == 403
    assert admin_upload.status_code == 201
