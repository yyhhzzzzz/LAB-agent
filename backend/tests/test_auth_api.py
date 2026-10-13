import asyncio

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.security import decode_access_token, verify_password
from app.db.models import User, UserRole, UserStatus
from app.db.session import create_database_engine, create_session_factory, initialize_database
from app.main import create_app


def test_password_hash_and_access_token_validation():
    from app.core.security import create_access_token, hash_password

    first_hash = hash_password("12345678")
    second_hash = hash_password("12345678")
    assert first_hash != second_hash
    assert verify_password("12345678", first_hash)
    assert not verify_password("wrong", first_hash)

    token = create_access_token("user-1", "test-secret", 1, now=100)
    assert decode_access_token(token, "test-secret", now=159) == "user-1"
    assert decode_access_token(token, "other-secret", now=159) is None
    assert decode_access_token(token, "test-secret", now=160) is None


def test_default_users_can_log_in_with_their_roles_and_hashed_passwords(tmp_path):
    database_file = tmp_path / "auth.db"
    database_url = "sqlite+aiosqlite:///{}".format(database_file)
    app = create_app(database_url=database_url)

    with TestClient(app) as client:
        for username, role in (
            ("stu", "student"),
            ("tec", "teacher"),
            ("admin", "admin"),
        ):
            response = client.post(
                "/api/v1/auth/login",
                json={"username": username, "password": "12345678"},
            )

            assert response.status_code == 200
            payload = response.json()
            assert payload["token_type"] == "bearer"
            assert payload["user"]["username"] == username
            assert payload["user"]["role"] == role
            assert "password_hash" not in payload["user"]

            assert decode_access_token(
                payload["access_token"], app.state.settings.auth_token_secret
            )

    async def load_seeded_users():
        engine = create_database_engine(database_url)
        try:
            session_factory = create_session_factory(engine)
            async with session_factory() as session:
                return list((await session.scalars(select(User))).all())
        finally:
            await engine.dispose()

    seeded_users = asyncio.run(load_seeded_users())
    by_username = {user.username: user for user in seeded_users}
    assert by_username["stu"].role is UserRole.STUDENT
    assert by_username["tec"].role is UserRole.TEACHER
    assert by_username["admin"].role is UserRole.ADMIN
    for username in ("stu", "tec", "admin"):
        user = by_username[username]
        assert user.password_hash != "12345678"
        assert verify_password("12345678", user.password_hash)


def test_login_rejects_bad_credentials_and_disabled_users(tmp_path):
    database_file = tmp_path / "auth-errors.db"
    database_url = "sqlite+aiosqlite:///{}".format(database_file)
    engine = create_database_engine(database_url)

    async def disable_student():
        try:
            await initialize_database(engine)
            session_factory = create_session_factory(engine)
            async with session_factory() as session:
                student = await session.scalar(select(User).where(User.username == "stu"))
                assert student is not None
                student.status = UserStatus.DISABLED
                await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(disable_student())
    app = create_app(database_url=database_url)

    with TestClient(app) as client:
        invalid_user = client.post(
            "/api/v1/auth/login",
            json={"username": "missing", "password": "12345678"},
        )
        invalid_password = client.post(
            "/api/v1/auth/login",
            json={"username": "stu", "password": "wrong"},
        )
        disabled_user = client.post(
            "/api/v1/auth/login",
            json={"username": "stu", "password": "12345678"},
        )

        assert invalid_user.status_code == invalid_password.status_code == disabled_user.status_code == 401
        assert invalid_user.json() == invalid_password.json()
        assert invalid_password.json() == disabled_user.json()


def test_default_user_seeding_does_not_reset_existing_accounts(tmp_path):
    database_file = tmp_path / "seed-idempotency.db"
    database_url = "sqlite+aiosqlite:///{}".format(database_file)
    engine = create_database_engine(database_url)

    async def update_and_reinitialize():
        try:
            await initialize_database(engine)
            session_factory = create_session_factory(engine)
            async with session_factory() as session:
                student = await session.scalar(select(User).where(User.username == "stu"))
                assert student is not None
                student.password_hash = "custom-existing-hash"
                student.role = UserRole.TEACHER
                await session.commit()

            await initialize_database(engine)
            async with session_factory() as session:
                student = await session.scalar(select(User).where(User.username == "stu"))
                assert student is not None
                assert student.password_hash == "custom-existing-hash"
                assert student.role is UserRole.TEACHER
        finally:
            await engine.dispose()

    asyncio.run(update_and_reinitialize())

    app = create_app(database_url=database_url)
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "stu", "password": "12345678"},
        )

        assert response.status_code == 401
