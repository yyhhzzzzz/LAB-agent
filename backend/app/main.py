from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from langchain_core.language_models.chat_models import BaseChatModel

from app.assistant.llm import create_chat_model
from app.api.auth import create_auth_router
from app.api.assistant import create_assistant_router
from app.api.documents import create_documents_router
from app.api.equipment import create_equipment_router
from app.api.college_labs import create_college_labs_router
from app.core.config import Settings
from app.db.session import (
    create_database_engine,
    create_session_factory,
    initialize_database,
)


def create_app(
    database_url: Optional[str] = None,
    assistant_model: Optional[BaseChatModel] = None,
) -> FastAPI:
    settings = Settings.from_env()
    db_engine = create_database_engine(database_url or settings.database_url)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        try:
            await initialize_database(db_engine)
            yield
        finally:
            await db_engine.dispose()

    app = FastAPI(title="Laboratory Equipment Assistant API", version="0.1.0", lifespan=lifespan)
    app.state.db_engine = db_engine
    app.state.db_session_factory = create_session_factory(db_engine)
    app.state.settings = settings
    app.include_router(
        create_assistant_router(
            settings,
            model_factory=lambda: assistant_model or create_chat_model(settings),
        )
    )
    app.include_router(create_auth_router(settings))
    app.include_router(create_documents_router(settings))
    app.include_router(create_equipment_router())
    app.include_router(create_college_labs_router())

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app


app = create_app()
