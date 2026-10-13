from langchain_openai import ChatOpenAI

from app.core.config import Settings


class ModelConfigurationError(ValueError):
    """The configured chat model cannot be initialized."""


def create_chat_model(settings: Settings) -> ChatOpenAI:
    if not settings.openai_api_key:
        raise ModelConfigurationError("OPENAI_API_KEY is not configured.")
    return ChatOpenAI(
        model=settings.chat_model_name,
        api_key=settings.openai_api_key,
        base_url=settings.openai_api_base or None,
        timeout=90,
        max_retries=1,
    )
