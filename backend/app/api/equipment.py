from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies import require_roles
from app.db.models import (
    Equipment,
    EquipmentStatus,
    Laboratory,
    User,
    UserRole,
    UserStatus,
    WorkOrder,
    WorkOrderPriority,
    WorkOrderStatus,
)
from app.db.session import get_db


class EquipmentCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    equipment_code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=160)
    laboratory_id: str = Field(min_length=1, max_length=36)
    category: Optional[str] = Field(default=None, max_length=100)
    model: Optional[str] = Field(default=None, max_length=120)
    manufacturer: Optional[str] = Field(default=None, max_length=160)
    serial_number: Optional[str] = Field(default=None, max_length=120)
    status: EquipmentStatus = EquipmentStatus.AVAILABLE
    description: Optional[str] = Field(default=None, max_length=10_000)

    @field_validator("category", "model", "manufacturer", "serial_number", "description")
    @classmethod
    def normalize_optional_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class EquipmentResponse(BaseModel):
    id: str
    equipment_code: str
    name: str
    category: Optional[str]
    model: Optional[str]
    manufacturer: Optional[str]
    serial_number: Optional[str]
    status: EquipmentStatus
    description: Optional[str]
    laboratory_id: Optional[str]
    laboratory_number: Optional[str]
    created_at: datetime


class WorkOrderCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    equipment_id: str = Field(min_length=1, max_length=36)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=10_000)
    priority: WorkOrderPriority = WorkOrderPriority.NORMAL


class WorkOrderResponse(BaseModel):
    id: str
    equipment_id: str
    equipment_code: str
    equipment_name: str
    requester_id: str
    requester_name: str
    title: str
    description: str
    priority: WorkOrderPriority
    status: WorkOrderStatus
    resolution: Optional[str] = None
    assignee_id: Optional[str] = None
    created_at: datetime


class WorkOrderStatusUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    status: WorkOrderStatus
    resolution: Optional[str] = Field(default=None, max_length=10_000)
    assignee_id: Optional[str] = Field(default=None, min_length=1, max_length=36)

    @field_validator("resolution")
    @classmethod
    def normalize_resolution(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


def _equipment_response(equipment: Equipment) -> EquipmentResponse:
    return EquipmentResponse(
        id=equipment.id,
        equipment_code=equipment.equipment_code,
        name=equipment.name,
        category=equipment.category,
        model=equipment.model,
        manufacturer=equipment.manufacturer,
        serial_number=equipment.serial_number,
        status=equipment.status,
        description=equipment.description,
        laboratory_id=equipment.laboratory_id,
        laboratory_number=(
            equipment.laboratory.laboratory_number if equipment.laboratory else None
        ),
        created_at=equipment.created_at,
    )


def _work_order_response(work_order: WorkOrder) -> WorkOrderResponse:
    return WorkOrderResponse(
        id=work_order.id,
        equipment_id=work_order.equipment_id,
        equipment_code=work_order.equipment.equipment_code,
        equipment_name=work_order.equipment.name,
        requester_id=work_order.requester_id,
        requester_name=work_order.requester.display_name,
        title=work_order.title,
        description=work_order.description,
        priority=work_order.priority,
        status=work_order.status,
        resolution=work_order.resolution,
        assignee_id=work_order.assignee_id,
        created_at=work_order.created_at,
    )


def _equipment_scope(statement, current_user: User):
    if current_user.role is UserRole.ADMIN:
        return statement
    if current_user.role is UserRole.TEACHER:
        return statement.join(Equipment.laboratory).where(
            Laboratory.manager_teacher_id == current_user.id
        )
    if current_user.college_id:
        return statement.join(Equipment.laboratory).where(
            Laboratory.college_id == current_user.college_id
        )
    return statement.where(False)


async def _get_accessible_equipment(
    session: AsyncSession, equipment_id: str, current_user: User
) -> Equipment:
    statement = select(Equipment).options(selectinload(Equipment.laboratory)).where(
        Equipment.id == equipment_id
    )
    equipment = await session.scalar(_equipment_scope(statement, current_user))
    if equipment is None:
        # Keep the not-found response opaque so callers cannot probe other colleges.
        raise HTTPException(status_code=404, detail="设备不存在或无权访问。")
    return equipment


def _work_order_scope(statement, current_user: User):
    if current_user.role is UserRole.ADMIN:
        return statement
    if current_user.role is UserRole.TEACHER:
        return statement.join(WorkOrder.equipment).join(Equipment.laboratory).where(
            Laboratory.manager_teacher_id == current_user.id
        )
    return statement.where(WorkOrder.requester_id == current_user.id)


def create_equipment_router() -> APIRouter:
    router = APIRouter(tags=["equipment", "work-orders"])
    equipment_managers = require_roles(UserRole.TEACHER, UserRole.ADMIN)
    work_order_users = require_roles(UserRole.STUDENT, UserRole.TEACHER, UserRole.ADMIN)

    @router.get("/api/v1/equipments", response_model=list[EquipmentResponse])
    async def list_equipments(
        session: AsyncSession = Depends(get_db),
        current_user: User = Depends(work_order_users),
    ) -> list[EquipmentResponse]:
        statement = _equipment_scope(
            select(Equipment).options(selectinload(Equipment.laboratory)), current_user
        )
        equipment = await session.scalars(
            statement.order_by(Equipment.created_at.desc(), Equipment.name)
        )
        return [_equipment_response(item) for item in equipment.all()]

    @router.post(
        "/api/v1/equipments",
        response_model=EquipmentResponse,
        status_code=status.HTTP_201_CREATED,
    )
    async def create_equipment(
        request: EquipmentCreate,
        session: AsyncSession = Depends(get_db),
        current_user: User = Depends(equipment_managers),
    ) -> EquipmentResponse:
        existing_code = await session.scalar(
            select(Equipment.id).where(Equipment.equipment_code == request.equipment_code)
        )
        if existing_code is not None:
            raise HTTPException(status_code=409, detail="设备编码已存在。")
        if request.serial_number:
            existing_serial = await session.scalar(
                select(Equipment.id).where(Equipment.serial_number == request.serial_number)
            )
            if existing_serial is not None:
                raise HTTPException(status_code=409, detail="设备序列号已存在。")

        laboratory = await session.get(Laboratory, request.laboratory_id)
        if laboratory is None:
            raise HTTPException(status_code=404, detail="实验室不存在。")
        if current_user.role is UserRole.TEACHER and (
            laboratory.manager_teacher_id != current_user.id
        ):
            raise HTTPException(status_code=403, detail="教师只能向自己管理的实验室添加设备。")

        equipment = Equipment(**request.model_dump())
        session.add(equipment)
        try:
            await session.commit()
        except IntegrityError as exc:
            await session.rollback()
            raise HTTPException(status_code=409, detail="设备编码或序列号已存在。") from exc
        await session.refresh(equipment)
        equipment.laboratory = laboratory
        return _equipment_response(equipment)

    @router.get("/api/v1/work-orders", response_model=list[WorkOrderResponse])
    async def list_work_orders(
        session: AsyncSession = Depends(get_db),
        current_user: User = Depends(work_order_users),
    ) -> list[WorkOrderResponse]:
        statement = _work_order_scope(select(WorkOrder), current_user).options(
            selectinload(WorkOrder.equipment), selectinload(WorkOrder.requester)
        )
        work_orders = await session.scalars(statement.order_by(WorkOrder.created_at.desc()))
        return [_work_order_response(item) for item in work_orders.all()]

    @router.post(
        "/api/v1/work-orders",
        response_model=WorkOrderResponse,
        status_code=status.HTTP_201_CREATED,
    )
    async def create_work_order(
        request: WorkOrderCreate,
        session: AsyncSession = Depends(get_db),
        current_user: User = Depends(work_order_users),
    ) -> WorkOrderResponse:
        equipment = await _get_accessible_equipment(session, request.equipment_id, current_user)

        work_order = WorkOrder(
            equipment_id=equipment.id,
            requester_id=current_user.id,
            title=request.title,
            description=request.description,
            priority=request.priority,
        )
        session.add(work_order)
        try:
            await session.commit()
        except IntegrityError as exc:
            await session.rollback()
            raise HTTPException(status_code=409, detail="设备或账号信息已发生变化，请重试。") from exc
        await session.refresh(work_order)
        work_order.equipment = equipment
        work_order.requester = current_user
        return _work_order_response(work_order)

    @router.patch("/api/v1/work-orders/{work_order_id}/status", response_model=WorkOrderResponse)
    async def update_work_order_status(
        work_order_id: str,
        request: WorkOrderStatusUpdate,
        session: AsyncSession = Depends(get_db),
        current_user: User = Depends(equipment_managers),
    ) -> WorkOrderResponse:
        statement = _work_order_scope(
            select(WorkOrder).where(WorkOrder.id == work_order_id), current_user
        ).options(
            selectinload(WorkOrder.equipment).selectinload(Equipment.laboratory),
            selectinload(WorkOrder.requester),
        )
        work_order = await session.scalar(statement)
        if work_order is None:
            raise HTTPException(status_code=404, detail="维修工单不存在或无权处理。")

        transitions = {
            WorkOrderStatus.SUBMITTED: {
                WorkOrderStatus.APPROVED,
                WorkOrderStatus.REJECTED,
                WorkOrderStatus.CANCELLED,
            },
            WorkOrderStatus.APPROVED: {
                WorkOrderStatus.IN_PROGRESS,
                WorkOrderStatus.CANCELLED,
            },
            WorkOrderStatus.IN_PROGRESS: {
                WorkOrderStatus.COMPLETED,
                WorkOrderStatus.CANCELLED,
            },
            WorkOrderStatus.COMPLETED: set(),
            WorkOrderStatus.REJECTED: set(),
            WorkOrderStatus.CANCELLED: set(),
        }
        if request.status not in transitions[work_order.status]:
            raise HTTPException(status_code=409, detail="不允许该维修工单状态流转。")
        if request.status is WorkOrderStatus.REJECTED and not request.resolution:
            raise HTTPException(status_code=422, detail="拒绝工单时必须填写处理说明。")
        if request.status is WorkOrderStatus.COMPLETED and not request.resolution:
            raise HTTPException(status_code=422, detail="完成工单时必须填写处理结果。")

        assignee = None
        assignee_id = request.assignee_id
        if assignee_id:
            assignee = await session.get(User, assignee_id)
            if assignee is None or assignee.status is not UserStatus.ACTIVE:
                raise HTTPException(status_code=422, detail="处理人不存在或已停用。")
            if assignee.role not in {UserRole.TEACHER, UserRole.ADMIN}:
                raise HTTPException(status_code=422, detail="处理人必须是教师或管理员。")
            laboratory = work_order.equipment.laboratory
            if assignee.role is UserRole.TEACHER and (
                laboratory is None or assignee.id != laboratory.manager_teacher_id
            ):
                raise HTTPException(status_code=422, detail="处理教师必须是设备所在实验室的管理教师。")
        elif request.status is WorkOrderStatus.APPROVED:
            assignee_id = current_user.id
            assignee = current_user

        work_order.status = request.status
        if request.resolution is not None:
            work_order.resolution = request.resolution
        if assignee_id is not None:
            work_order.assignee_id = assignee_id
            work_order.assigned_at = datetime.now(timezone.utc)
        if request.status is WorkOrderStatus.COMPLETED:
            work_order.completed_at = datetime.now(timezone.utc)
        await session.commit()
        await session.refresh(work_order)
        return _work_order_response(work_order)

    return router
