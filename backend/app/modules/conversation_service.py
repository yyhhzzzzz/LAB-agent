from typing import Dict, List, Optional
from uuid import uuid4

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Conversation,
    ConversationMessage,
    Equipment,
    MessageRole,
)


MAX_MEMORY_MESSAGES = 24
MAX_MEMORY_CHARS = 12000
MAX_RESTORED_MESSAGES = 100


class ConversationNotFound(LookupError):
    """The conversation does not exist or is not owned by the requesting user."""


class ConversationScopeMismatch(ValueError):
    """The equipment scope cannot change after a conversation has started."""


class ConversationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_conversations(self, owner_user_id: str) -> List[Conversation]:
        """Return only this user's conversations, most recently updated first."""
        rows = await self.session.scalars(
            select(Conversation)
            .where(Conversation.user_id == owner_user_id)
            .order_by(
                Conversation.updated_at.desc(),
                Conversation.created_at.desc(),
                Conversation.id,
            )
        )
        return list(rows)

    async def start_or_resume(
        self,
        owner_user_id: str,
        conversation_id: Optional[str],
        equipment_selector: Optional[str],
        initial_query: str,
    ) -> tuple[Conversation, List[Dict[str, str]]]:
        normalized_equipment = _normalize_equipment_selector(equipment_selector)
        if conversation_id:
            conversation = await self.session.scalar(
                select(Conversation).where(
                    Conversation.id == conversation_id,
                    Conversation.user_id == owner_user_id,
                )
            )
            if conversation is None:
                raise ConversationNotFound("Conversation not found.")
            first_user_message = await self.session.scalar(
                select(ConversationMessage)
                .where(
                    ConversationMessage.conversation_id == conversation.id,
                    ConversationMessage.role == MessageRole.USER,
                )
                .order_by(ConversationMessage.sequence)
                .limit(1)
            )
            if first_user_message is not None:
                stored_scope = _normalize_equipment_selector(
                    (first_user_message.metadata_json or {}).get("equipment_selector")
                )
                if stored_scope != normalized_equipment:
                    raise ConversationScopeMismatch(
                        "The equipment scope cannot change within a conversation."
                    )
            elif conversation.equipment_id != await self._resolve_equipment_id(
                normalized_equipment
            ):
                raise ConversationScopeMismatch(
                    "The equipment scope cannot change within a conversation."
                )
        else:
            conversation = Conversation(
                id=str(uuid4()),
                user_id=owner_user_id,
                equipment_id=await self._resolve_equipment_id(normalized_equipment),
                title=initial_query[:255],
            )
            self.session.add(conversation)
            await self.session.flush()
            await self.session.commit()

        history = await self._load_memory(conversation.id, normalized_equipment)
        return conversation, history

    async def save_turn(
        self,
        conversation_id: str,
        query: str,
        answer: str,
        equipment_selector: Optional[str],
        sources: List[dict],
        status: str,
    ) -> None:
        max_sequence = await self.session.scalar(
            select(func.max(ConversationMessage.sequence)).where(
                ConversationMessage.conversation_id == conversation_id
            )
        )
        sequence = int(max_sequence or -1) + 1
        message_scope = {"equipment_selector": _normalize_equipment_selector(equipment_selector)}
        self.session.add_all(
            [
                ConversationMessage(
                    conversation_id=conversation_id,
                    sequence=sequence,
                    role=MessageRole.USER,
                    content=query,
                    metadata_json=message_scope,
                ),
                ConversationMessage(
                    conversation_id=conversation_id,
                    sequence=sequence + 1,
                    role=MessageRole.ASSISTANT,
                    content=answer,
                    metadata_json={
                        **message_scope,
                        "sources": sources,
                        "status": status,
                    },
                ),
            ]
        )
        conversation = await self.session.get(Conversation, conversation_id)
        if conversation is not None:
            conversation.updated_at = func.now()
        await self.session.commit()

    async def get_history(
        self,
        owner_user_id: str,
        conversation_id: str,
    ) -> tuple[Conversation, List[dict], Optional[str]]:
        conversation = await self.session.scalar(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.user_id == owner_user_id,
            )
        )
        if conversation is None:
            raise ConversationNotFound("Conversation not found.")

        messages = await self.session.scalars(
            select(ConversationMessage)
            .where(ConversationMessage.conversation_id == conversation_id)
            .order_by(ConversationMessage.sequence)
            .limit(MAX_RESTORED_MESSAGES)
        )
        restored = []
        equipment_selector = None
        scope_was_loaded = False
        for message in messages:
            metadata = message.metadata_json or {}
            if not scope_was_loaded and message.role is MessageRole.USER:
                equipment_selector = _normalize_equipment_selector(
                    metadata.get("equipment_selector")
                )
                scope_was_loaded = True
            restored.append(
                {
                    "id": message.id,
                    "role": message.role.value,
                    "content": message.content,
                    "sources": metadata.get("sources", []),
                    "status": metadata.get("status"),
                }
            )
        return conversation, restored, equipment_selector

    async def _resolve_equipment_id(self, equipment_selector: Optional[str]) -> Optional[str]:
        if not equipment_selector:
            return None
        return await self.session.scalar(
            select(Equipment.id).where(
                or_(
                    Equipment.id == equipment_selector,
                    Equipment.equipment_code == equipment_selector,
                )
            )
        )

    async def _load_memory(
        self,
        conversation_id: str,
        equipment_selector: Optional[str],
    ) -> List[Dict[str, str]]:
        rows = await self.session.scalars(
            select(ConversationMessage)
            .where(ConversationMessage.conversation_id == conversation_id)
            .order_by(ConversationMessage.sequence.desc())
            .limit(MAX_MEMORY_MESSAGES)
        )
        relevant = [
            row
            for row in reversed(list(rows))
            if (row.metadata_json or {}).get("equipment_selector") == equipment_selector
        ]

        memory = []
        remaining_chars = MAX_MEMORY_CHARS
        for row in reversed(relevant):
            if remaining_chars <= 0:
                break
            content = row.content
            if len(content) > remaining_chars:
                content = content[-remaining_chars:]
            memory.append({"role": row.role.value, "content": content})
            remaining_chars -= len(content)
        return list(reversed(memory))


def _normalize_equipment_selector(value: Optional[str]) -> Optional[str]:
    normalized = (value or "").strip()
    return normalized or None
