from fastapi.testclient import TestClient

from app.main import create_app


def login(
    client: TestClient, username: str, password: str = "12345678"
) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login", json={"username": username, "password": password}
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def user_id(client: TestClient, username: str) -> str:
    return client.post(
        "/api/v1/auth/login", json={"username": username, "password": "12345678"}
    ).json()["user"]["id"]


def test_admin_creates_college_and_same_college_laboratory(tmp_path):
    app = create_app(database_url=f"sqlite+aiosqlite:///{(tmp_path / 'org.db').as_posix()}")
    with TestClient(app) as client:
        admin = login(client, "admin")
        teacher = login(client, "tec")
        college = client.post("/api/v1/colleges", json={"name": "理学院"}, headers=admin)
        assert college.status_code == 201
        college_id = college.json()["id"]
        teacher_id = user_id(client, "tec")
        assert client.patch(
            f"/api/v1/users/{teacher_id}/college",
            json={"college_id": college_id},
            headers=admin,
        ).status_code == 200
        laboratory = client.post(
            "/api/v1/laboratories",
            json={
                "laboratory_number": "101",
                "college_id": college_id,
                "manager_teacher_id": teacher_id,
            },
            headers=admin,
        )
        assert laboratory.status_code == 201
        duplicate = client.post(
            "/api/v1/laboratories",
            json={
                "laboratory_number": "101",
                "college_id": college_id,
                "manager_teacher_id": teacher_id,
            },
            headers=admin,
        )
        assert duplicate.status_code == 409
        assert client.get("/api/v1/laboratories", headers=teacher).json()[0][
            "laboratory_number"
        ] == "101"


def test_cross_college_laboratory_manager_and_student_creation_are_rejected(tmp_path):
    app = create_app(database_url=f"sqlite+aiosqlite:///{(tmp_path / 'org.db').as_posix()}")
    with TestClient(app) as client:
        admin = login(client, "admin")
        teacher = login(client, "tec")
        student = login(client, "stu")
        first = client.post("/api/v1/colleges", json={"name": "一学院"}, headers=admin).json()
        second = client.post("/api/v1/colleges", json={"name": "二学院"}, headers=admin).json()
        teacher_id = user_id(client, "tec")
        client.patch(
            f"/api/v1/users/{teacher_id}/college",
            json={"college_id": first["id"]},
            headers=admin,
        )
        cross_lab = client.post(
            "/api/v1/laboratories",
            json={
                "laboratory_number": "201",
                "college_id": second["id"],
                "manager_teacher_id": teacher_id,
            },
            headers=admin,
        )
        assert cross_lab.status_code == 422
        cross_student = client.post(
            "/api/v1/users/students",
            json={
                "username": "student-two",
                "password": "12345678",
                "display_name": "Student Two",
                "college_id": second["id"],
            },
            headers=teacher,
        )
        assert cross_student.status_code == 403
        student = client.post(
            "/api/v1/users/students",
            json={
                "username": "student-one",
                "password": "12345678",
                "display_name": "Student One",
                "college_id": first["id"],
            },
            headers=teacher,
        )
        assert student.status_code == 201
        assert student.json()["college_id"] == first["id"]


def test_admin_creates_teacher_with_college_and_credentials(tmp_path):
    app = create_app(database_url=f"sqlite+aiosqlite:///{(tmp_path / 'org.db').as_posix()}")
    with TestClient(app) as client:
        admin = login(client, "admin")
        college = client.post(
            "/api/v1/colleges", json={"name": "工程学院"}, headers=admin
        ).json()

        response = client.post(
            "/api/v1/users/teachers",
            json={
                "username": "teacher-new",
                "password": "secure-pass-1",
                "display_name": "新教师",
                "college_id": college["id"],
                "email": "  TEACHER@EXAMPLE.COM  ",
            },
            headers=admin,
        )

        assert response.status_code == 201
        created_teacher = response.json()
        assert created_teacher["username"] == "teacher-new"
        assert created_teacher["display_name"] == "新教师"
        assert created_teacher["college_id"] == college["id"]
        authenticated_teacher = client.post(
            "/api/v1/auth/login",
            json={"username": "teacher-new", "password": "secure-pass-1"},
        )
        assert authenticated_teacher.status_code == 200
        assert authenticated_teacher.json()["user"]["role"] == "teacher"
        teachers = client.get("/api/v1/users/teachers", headers=admin).json()
        assert any(item["id"] == created_teacher["id"] for item in teachers)


def test_teacher_creation_requires_admin_and_valid_college(tmp_path):
    app = create_app(database_url=f"sqlite+aiosqlite:///{(tmp_path / 'org.db').as_posix()}")
    with TestClient(app) as client:
        admin = login(client, "admin")
        teacher = login(client, "tec")
        student = login(client, "stu")
        first = client.post("/api/v1/colleges", json={"name": "一学院"}, headers=admin).json()
        second = client.post("/api/v1/colleges", json={"name": "二学院"}, headers=admin).json()
        teacher_id = user_id(client, "tec")
        assert client.patch(
            f"/api/v1/users/{teacher_id}/college",
            json={"college_id": first["id"]},
            headers=admin,
        ).status_code == 200

        payload = {
            "username": "teacher-cross-college",
            "password": "secure-pass-1",
            "display_name": "跨学院教师",
            "college_id": second["id"],
        }
        assert client.post("/api/v1/users/teachers", json=payload, headers=teacher).status_code == 403
        assert client.post("/api/v1/users/teachers", json=payload, headers=student).status_code == 403
        assert client.post(
            "/api/v1/users/teachers",
            json={**payload, "username": "teacher-no-college", "college_id": "missing-college"},
            headers=admin,
        ).status_code == 404
        assert client.post(
            "/api/v1/users/teachers",
            json={**payload, "username": "teacher-short-password", "password": "short"},
            headers=admin,
        ).status_code == 422


def test_teacher_creation_rejects_duplicate_username_and_email(tmp_path):
    app = create_app(database_url=f"sqlite+aiosqlite:///{(tmp_path / 'org.db').as_posix()}")
    with TestClient(app) as client:
        admin = login(client, "admin")
        college = client.post(
            "/api/v1/colleges", json={"name": "信息学院"}, headers=admin
        ).json()
        payload = {
            "username": "teacher-unique",
            "password": "secure-pass-1",
            "display_name": "教师账号",
            "college_id": college["id"],
            "email": "teacher@example.com",
        }
        assert client.post("/api/v1/users/teachers", json=payload, headers=admin).status_code == 201
        duplicate_username = client.post(
            "/api/v1/users/teachers",
            json={**payload, "email": "another@example.com"},
            headers=admin,
        )
        duplicate_email = client.post(
            "/api/v1/users/teachers",
            json={**payload, "username": "another-teacher", "email": " TEACHER@example.com "},
            headers=admin,
        )
        assert duplicate_username.status_code == 409
        assert duplicate_email.status_code == 409
