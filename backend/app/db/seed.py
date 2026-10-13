from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from app.core.security import hash_password
from app.db.models import User, UserRole, UserStatus


_DEFAULT_USERS = (
    ("stu", "学生", UserRole.STUDENT),
    ("tec", "教师", UserRole.TEACHER),
    ("admin", "管理员", UserRole.ADMIN),
)
_DEFAULT_PASSWORD = "12345678"


async def seed_default_users(engine: AsyncEngine) -> None:
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    usernames = [username for username, _, _ in _DEFAULT_USERS]
    async with session_factory() as session:
        existing = set(
            (await session.scalars(select(User.username).where(User.username.in_(usernames)))).all()
        )
        missing = [user for user in _DEFAULT_USERS if user[0] not in existing]
        if not missing:
            return

        values = [
            {
                "id": str(uuid4()),
                "username": username,
                "password_hash": hash_password(_DEFAULT_PASSWORD),
                "display_name": display_name,
                "role": role,
                "status": UserStatus.ACTIVE,
            }
            for username, display_name, role in missing
        ]
        if engine.dialect.name == "sqlite":
            statement = sqlite_insert(User).values(values).on_conflict_do_nothing(
                index_elements=[User.username]
            )
        elif engine.dialect.name == "postgresql":
            statement = postgresql_insert(User).values(values).on_conflict_do_nothing(
                index_elements=[User.username]
            )
        else:
            raise ValueError("Default user seeding supports SQLite and PostgreSQL")

        await session.execute(statement)
        await session.commit()
