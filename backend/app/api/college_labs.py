from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette.concurrency import run_in_threadpool

from app.api.dependencies import get_current_user, require_roles
from app.core.security import hash_password
from app.db.models import College, Laboratory, User, UserRole, UserStatus
from app.db.session import get_db


class CollegeCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    name: str = Field(min_length=1, max_length=120)


class CollegeResponse(BaseModel):
    id: str
    name: str


class LaboratoryCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    laboratory_number: str = Field(min_length=1, max_length=64)
    college_id: str = Field(min_length=1, max_length=36)
    manager_teacher_id: str = Field(min_length=1, max_length=36)


class LaboratoryResponse(BaseModel):
    id: str
    laboratory_number: str
    college_id: str
    manager_teacher_id: str
    manager_name: str


class CollegeUserCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=120)
    college_id: str = Field(min_length=1, max_length=36)
    email: Optional[str] = Field(default=None, max_length=254)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = value.strip().lower()
        return normalized or None


class StudentCreate(CollegeUserCreate):
    pass


class TeacherCreate(CollegeUserCreate):
    pass


class UserCollegeUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    college_id: str = Field(min_length=1, max_length=36)


class UserResponse(BaseModel):
    id: str
    username: str
    display_name: str
    college_id: Optional[str]


async def _create_college_user(
    request: CollegeUserCreate,
    role: UserRole,
    session: AsyncSession,
) -> User:
    college = await session.get(College, request.college_id)
    if college is None:
        raise HTTPException(status_code=404, detail="学院不存在。")
    existing_user = await session.scalar(
        select(User.id).where(User.username == request.username)
    )
    if existing_user is not None:
        raise HTTPException(status_code=409, detail="用户名已存在。")
    if request.email is not None:
        existing_email = await session.scalar(
            select(User.id).where(User.email == request.email)
        )
        if existing_email is not None:
            raise HTTPException(status_code=409, detail="邮箱已存在。")

    user = User(
        username=request.username,
        password_hash=await run_in_threadpool(hash_password, request.password),
        display_name=request.display_name,
        email=request.email,
        role=role,
        status=UserStatus.ACTIVE,
        college_id=college.id,
    )
    session.add(user)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=409, detail="用户名或邮箱已存在。") from exc
    await session.refresh(user)
    return user


def _laboratory_response(laboratory: Laboratory) -> LaboratoryResponse:
    return LaboratoryResponse(
        id=laboratory.id,
        laboratory_number=laboratory.laboratory_number,
        college_id=laboratory.college_id,
        manager_teacher_id=laboratory.manager_teacher_id,
        manager_name=laboratory.manager_teacher.display_name,
    )


def create_college_labs_router() -> APIRouter:
    router = APIRouter(tags=["colleges", "laboratories", "users"])

    @router.get("/api/v1/colleges", response_model=list[CollegeResponse])
    async def list_colleges(
        session: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> list[CollegeResponse]:
        statement = select(College).order_by(College.name)
        if current_user.role is not UserRole.ADMIN:
            if current_user.college_id is None:
                return []
            statement = statement.where(College.id == current_user.college_id)
        colleges = (await session.scalars(statement)).all()
        return [CollegeResponse(id=item.id, name=item.name) for item in colleges]

    @router.post(
        "/api/v1/colleges",
        response_model=CollegeResponse,
        status_code=status.HTTP_201_CREATED,
    )
    async def create_college(
        request: CollegeCreate,
        session: AsyncSession = Depends(get_db),
        _current_user: User = Depends(require_roles(UserRole.ADMIN)),
    ) -> CollegeResponse:
        college = College(name=request.name)
        session.add(college)
        try:
            await session.commit()
        except IntegrityError as exc:
            await session.rollback()
            raise HTTPException(status_code=409, detail="学院名称已存在。") from exc
        await session.refresh(college)
        return CollegeResponse(id=college.id, name=college.name)

    @router.get("/api/v1/laboratories", response_model=list[LaboratoryResponse])
    async def list_laboratories(
        session: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> list[LaboratoryResponse]:
        statement = select(Laboratory).options(selectinload(Laboratory.manager_teacher))
        if current_user.role is UserRole.ADMIN:
            pass
        elif current_user.role is UserRole.TEACHER:
            statement = statement.where(
                Laboratory.manager_teacher_id == current_user.id
            )
        elif current_user.college_id:
            statement = statement.where(Laboratory.college_id == current_user.college_id)
        else:
            return []
        laboratories = (await session.scalars(statement.order_by(Laboratory.laboratory_number))).all()
        return [_laboratory_response(item) for item in laboratories]

    @router.post(
        "/api/v1/laboratories",
        response_model=LaboratoryResponse,
        status_code=status.HTTP_201_CREATED,
    )
    async def create_laboratory(
        request: LaboratoryCreate,
        session: AsyncSession = Depends(get_db),
        _current_user: User = Depends(require_roles(UserRole.ADMIN)),
    ) -> LaboratoryResponse:
        college = await session.get(College, request.college_id)
        if college is None:
            raise HTTPException(status_code=404, detail="学院不存在。")
        manager = await session.get(User, request.manager_teacher_id)
        if manager is None or manager.role is not UserRole.TEACHER:
            raise HTTPException(status_code=422, detail="管理者必须是教师账号。")
        if manager.status is not UserStatus.ACTIVE:
            raise HTTPException(status_code=422, detail="管理教师账号已停用。")
        if manager.college_id != college.id:
            raise HTTPException(status_code=422, detail="管理教师必须属于实验室所在学院。")

        laboratory = Laboratory(
            laboratory_number=request.laboratory_number,
            college_id=college.id,
            manager_teacher_id=manager.id,
        )
        session.add(laboratory)
        try:
            await session.commit()
        except IntegrityError as exc:
            await session.rollback()
            raise HTTPException(status_code=409, detail="该学院内的实验室编号已存在。") from exc
        await session.refresh(laboratory)
        laboratory.manager_teacher = manager
        return _laboratory_response(laboratory)

    @router.get("/api/v1/users/teachers", response_model=list[UserResponse])
    async def list_teachers(
        session: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> list[UserResponse]:
        if current_user.role is UserRole.STUDENT:
            raise HTTPException(status_code=403, detail="当前账号没有执行此操作的权限")
        statement = select(User).where(
            User.role == UserRole.TEACHER,
            User.status == UserStatus.ACTIVE,
        )
        if current_user.role is UserRole.TEACHER:
            if current_user.college_id is None:
                return []
            statement = statement.where(User.college_id == current_user.college_id)
        teachers = (await session.scalars(statement.order_by(User.display_name))).all()
        return [
            UserResponse(
                id=item.id,
                username=item.username,
                display_name=item.display_name,
                college_id=item.college_id,
            )
            for item in teachers
        ]

    @router.get("/api/v1/users/students", response_model=list[UserResponse])
    async def list_students(
        session: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> list[UserResponse]:
        if current_user.role is UserRole.STUDENT:
            raise HTTPException(status_code=403, detail="当前账号没有执行此操作的权限")
        statement = select(User).where(
            User.role == UserRole.STUDENT,
            User.status == UserStatus.ACTIVE,
        )
        if current_user.role is UserRole.TEACHER:
            if current_user.college_id is None:
                return []
            statement = statement.where(User.college_id == current_user.college_id)
        students = (await session.scalars(statement.order_by(User.display_name))).all()
        return [
            UserResponse(
                id=item.id,
                username=item.username,
                display_name=item.display_name,
                college_id=item.college_id,
            )
            for item in students
        ]

    @router.post(
        "/api/v1/users/students",
        response_model=UserResponse,
        status_code=status.HTTP_201_CREATED,
    )
    async def create_student(
        request: StudentCreate,
        session: AsyncSession = Depends(get_db),
        current_user: User = Depends(require_roles(UserRole.TEACHER, UserRole.ADMIN)),
    ) -> UserResponse:
        if current_user.role is UserRole.TEACHER and request.college_id != current_user.college_id:
            raise HTTPException(status_code=403, detail="教师只能添加本学院学生。")
        student = await _create_college_user(request, UserRole.STUDENT, session)
        return UserResponse(
            id=student.id,
            username=student.username,
            display_name=student.display_name,
            college_id=student.college_id,
        )

    @router.post(
        "/api/v1/users/teachers",
        response_model=UserResponse,
        status_code=status.HTTP_201_CREATED,
    )
    async def create_teacher(
        request: TeacherCreate,
        session: AsyncSession = Depends(get_db),
        _current_user: User = Depends(require_roles(UserRole.ADMIN)),
    ) -> UserResponse:
        teacher = await _create_college_user(request, UserRole.TEACHER, session)
        return UserResponse(
            id=teacher.id,
            username=teacher.username,
            display_name=teacher.display_name,
            college_id=teacher.college_id,
        )

    @router.patch("/api/v1/users/{user_id}/college", response_model=UserResponse)
    async def update_user_college(
        user_id: str,
        request: UserCollegeUpdate,
        session: AsyncSession = Depends(get_db),
        _current_user: User = Depends(require_roles(UserRole.ADMIN)),
    ) -> UserResponse:
        user = await session.get(User, user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="用户不存在。")
        if user.role not in {UserRole.TEACHER, UserRole.STUDENT}:
            raise HTTPException(status_code=422, detail="只能为教师或学生绑定学院。")
        college = await session.get(College, request.college_id)
        if college is None:
            raise HTTPException(status_code=404, detail="学院不存在。")
        if user.role is UserRole.TEACHER and user.college_id != college.id:
            managed_count = await session.scalar(
                select(Laboratory.id).where(Laboratory.manager_teacher_id == user.id).limit(1)
            )
            if managed_count is not None:
                raise HTTPException(
                    status_code=409,
                    detail="教师仍管理实验室，不能更改所属学院。",
                )
        user.college_id = college.id
        await session.commit()
        await session.refresh(user)
        return UserResponse(
            id=user.id,
            username=user.username,
            display_name=user.display_name,
            college_id=user.college_id,
        )

    return router
