import logging
from datetime import datetime
from typing import Callable, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from langchain_core.language_models.chat_models import BaseChatModel

from app.assistant.document_assistant import CitationSource, DocumentAssistant
from app.assistant.llm import ModelConfigurationError
from app.api.dependencies import get_current_user
from app.core.config import Settings
from app.db.models import Conversation, ConversationStatus, Equipment, Laboratory, User, UserRole
from app.db.session import get_db
from app.modules.conversation_service import (
    ConversationService,
    ConversationNotFound,
    ConversationScopeMismatch,
)

logger = logging.getLogger(__name__)


async def _ensure_equipment_access(
    session: AsyncSession,
    current_user: User,
    equipment_selector: Optional[str],
) -> None:
    """Prevent direct Assistant requests from bypassing the equipment list scope."""
    selector = (equipment_selector or "").strip()
    if not selector or current_user.role is UserRole.ADMIN or current_user.college_id is None:
        return

    statement = select(Equipment.id).join(Equipment.laboratory).where(
        or_(Equipment.id == selector, Equipment.equipment_code == selector)
    )
    if current_user.role is UserRole.TEACHER:
        statement = statement.where(Laboratory.manager_teacher_id == current_user.id)
    else:
        statement = statement.where(Laboratory.college_id == current_user.college_id)
    if await session.scalar(statement) is None:
        raise HTTPException(status_code=404, detail="设备不存在或无权访问。")


class AssistantChatRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    equipment_id: Optional[str] = Field(default=None, max_length=100)
    conversation_id: Optional[str] = Field(default=None, min_length=36, max_length=36)


class AssistantChatResponse(BaseModel):
    conversation_id: str
    query: str
    answer: str
    status: str
    sources: List[CitationSource]


class ConversationMessageResponse(BaseModel):
    id: str
    role: str
    content: str
    sources: List[CitationSource] = Field(default_factory=list)
    status: Optional[str] = None


class ConversationHistoryResponse(BaseModel):
    conversation_id: str
    equipment_id: Optional[str]
    equipment_selector: Optional[str] = None
    messages: List[ConversationMessageResponse]


class ConversationListItemResponse(BaseModel):
    id: str
    title: Optional[str]
    updated_at: datetime
    equipment_id: Optional[str]
    status: ConversationStatus


def _conversation_list_item(conversation: Conversation) -> ConversationListItemResponse:
    return ConversationListItemResponse(
        id=conversation.id,
        title=conversation.title,
        updated_at=conversation.updated_at,
        equipment_id=conversation.equipment_id,
        status=conversation.status,
    )


def create_assistant_router(
    settings: Settings,
    model_factory: Callable[[], BaseChatModel],
) -> APIRouter:
    assistant_router = APIRouter(prefix="/api/v1/assistant", tags=["assistant"])

    @assistant_router.get(
        "/conversations",
        response_model=List[ConversationListItemResponse],
    )
    async def list_conversations(
        session: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> List[ConversationListItemResponse]:
        conversations = await ConversationService(session).list_conversations(
            current_user.id
        )
        return [_conversation_list_item(conversation) for conversation in conversations]

    @assistant_router.post("/chat", response_model=AssistantChatResponse)
    async def chat(
        request: AssistantChatRequest,
        session: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> AssistantChatResponse:
        query = request.query.strip()
        if not query:
            raise HTTPException(status_code=422, detail="A question is required.")
        await _ensure_equipment_access(session, current_user, request.equipment_id)
        conversations = ConversationService(session)
        try:
            conversation, history = await conversations.start_or_resume(
                owner_user_id=current_user.id,
                conversation_id=request.conversation_id,
                equipment_selector=request.equipment_id,
                initial_query=query,
            )
            assistant = DocumentAssistant(
                session=session,
                model_factory=model_factory,
                max_context_chars=settings.document_context_max_chars,
            )
            result = await assistant.invoke(
                query,
                request.equipment_id.strip() if request.equipment_id else None,
                history,
            )
            if result["status"] == "context_too_large":
                raise HTTPException(status_code=413, detail=result["answer"])
            await conversations.save_turn(
                conversation_id=conversation.id,
                query=query,
                answer=result["answer"],
                equipment_selector=request.equipment_id,
                sources=result["citations"],
                status=result["status"],
            )
        except ModelConfigurationError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except ConversationNotFound as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ConversationScopeMismatch as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("Assistant response generation failed")
            raise HTTPException(
                status_code=503,
                detail="Assistant response generation failed.",
            ) from exc

        return AssistantChatResponse(
            conversation_id=conversation.id,
            query=query,
            answer=result["answer"],
            status=result["status"],
            sources=result["citations"],
        )

    @assistant_router.get(
        "/conversations/{conversation_id}",
        response_model=ConversationHistoryResponse,
    )
    async def get_conversation(
        conversation_id: str,
        session: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> ConversationHistoryResponse:
        try:
            conversation, messages, equipment_selector = await ConversationService(
                session
            ).get_history(current_user.id, conversation_id)
        except ConversationNotFound as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return ConversationHistoryResponse(
            conversation_id=conversation.id,
            equipment_id=conversation.equipment_id,
            equipment_selector=equipment_selector,
            messages=messages,
        )

    return assistant_router
