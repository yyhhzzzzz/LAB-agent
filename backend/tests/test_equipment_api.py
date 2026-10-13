from fastapi.testclient import TestClient

from app.main import create_app


def _headers(client: TestClient, username: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "12345678"},
    )
    assert response.status_code == 200
    return {"Authorization": "Bearer " + response.json()["access_token"]}


def _configure_default_users(client: TestClient) -> tuple[dict, dict, dict, dict]:
    admin = _headers(client, "admin")
    student = _headers(client, "stu")
    teacher = _headers(client, "tec")
    college = client.post("/api/v1/colleges", json={"name": "工程学院"}, headers=admin)
    assert college.status_code == 201
    college_id = college.json()["id"]
    for headers, username in ((student, "stu"), (teacher, "tec")):
        user_id = _user_id(client, headers, username)
        response = client.patch(
            f"/api/v1/users/{user_id}/college",
            json={"college_id": college_id},
            headers=admin,
        )
        assert response.status_code == 200
    teacher_id = _user_id(client, teacher, "tec")
    laboratory = client.post(
        "/api/v1/laboratories",
        json={
            "laboratory_number": "A-101",
            "college_id": college_id,
            "manager_teacher_id": teacher_id,
        },
        headers=admin,
    )
    assert laboratory.status_code == 201
    return admin, student, teacher, laboratory.json()


def _user_id(client: TestClient, headers: dict[str, str], username: str) -> str:
    login = client.post(
        "/api/v1/auth/login", json={"username": username, "password": "12345678"}
    )
    assert login.status_code == 200
    assert headers["Authorization"].startswith("Bearer ")
    return login.json()["user"]["id"]


def test_equipment_and_work_order_lifecycle_and_permissions(tmp_path):
    app = create_app(
        database_url="sqlite+aiosqlite:///{}".format((tmp_path / "equipment.db").as_posix())
    )

    with TestClient(app) as client:
        admin, student, teacher, laboratory = _configure_default_users(client)

        assert client.get("/api/v1/equipments").status_code == 401
        assert client.get("/api/v1/equipments", headers=student).status_code == 200
        assert client.post(
            "/api/v1/equipments",
            json={"equipment_code": "CENT-01", "name": "离心机", "laboratory_id": laboratory["id"]},
            headers=student,
        ).status_code == 403

        created = client.post(
            "/api/v1/equipments",
            json={
                "equipment_code": " CENT-01 ",
                "name": " 离心机 ",
                "serial_number": "SN-01",
                "status": "available",
                "laboratory_id": laboratory["id"],
            },
            headers=teacher,
        )
        assert created.status_code == 201
        equipment = created.json()
        assert equipment["laboratory_id"] == laboratory["id"]
        assert equipment["laboratory_number"] == "A-101"

        duplicate_code = client.post(
            "/api/v1/equipments",
            json={
                "equipment_code": "CENT-01",
                "name": "另一台",
                "laboratory_id": laboratory["id"],
            },
            headers=teacher,
        )
        duplicate_serial = client.post(
            "/api/v1/equipments",
            json={
                "equipment_code": "CENT-02",
                "name": "另一台",
                "serial_number": "SN-01",
                "laboratory_id": laboratory["id"],
            },
            headers=teacher,
        )
        assert duplicate_code.status_code == duplicate_serial.status_code == 409

        order = client.post(
            "/api/v1/work-orders",
            json={
                "equipment_id": equipment["id"],
                "title": "维修",
                "description": "无法启动",
                "priority": "urgent",
            },
            headers=student,
        )
        assert order.status_code == 201
        order_body = order.json()
        assert order_body["requester_id"] == _user_id(client, student, "stu")
        assert order_body["status"] == "submitted"
        assert order_body["priority"] == "urgent"

        teacher_orders = client.get("/api/v1/work-orders", headers=teacher)
        assert teacher_orders.status_code == 200
        assert teacher_orders.json()[0]["id"] == order_body["id"]
        approved = client.patch(
            f"/api/v1/work-orders/{order_body['id']}/status",
            json={"status": "approved"},
            headers=teacher,
        )
        assert approved.status_code == 200
        assert approved.json()["status"] == "approved"

        student_orders = client.get("/api/v1/work-orders", headers=student)
        assert student_orders.status_code == 200
        assert student_orders.json()[0]["id"] == order_body["id"]

        other_college = client.post(
            "/api/v1/colleges", json={"name": "信息学院"}, headers=admin
        )
        assert other_college.status_code == 201
        student_id = _user_id(client, student, "stu")
        moved = client.patch(
            f"/api/v1/users/{student_id}/college",
            json={"college_id": other_college.json()["id"]},
            headers=admin,
        )
        assert moved.status_code == 200
        assert client.get("/api/v1/equipments", headers=student).json() == []
        cross_college_order = client.post(
            "/api/v1/work-orders",
            json={
                "equipment_id": equipment["id"],
                "title": "越权报修",
                "description": "不应访问其他学院设备",
            },
            headers=student,
        )
        assert cross_college_order.status_code == 404


def test_work_order_validation_and_student_access(tmp_path):
    app = create_app(
        database_url="sqlite+aiosqlite:///{}".format((tmp_path / "work-orders.db").as_posix())
    )

    with TestClient(app) as client:
        student = _headers(client, "stu")
        assert client.get("/api/v1/work-orders", headers=student).status_code == 200
        teacher = _headers(client, "tec")
        invalid = client.post(
            "/api/v1/work-orders",
            json={"equipment_id": "", "title": "", "description": ""},
            headers=teacher,
        )
        assert invalid.status_code == 422
