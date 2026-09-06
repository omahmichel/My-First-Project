from django.utils import timezone

from .context import (
    build_context_evidence,
    build_verified_intelligence_context,
)
from .prompts import (
    build_analyst_instructions,
    build_conversation_text,
)
from .provider import (
    AIProviderError,
    AIProviderNotConfigured,
    get_ai_provider,
)


class AIAnalystUnavailable(Exception):
    def __init__(self, *, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


def answer_business_question(
    *,
    business,
    question,
    history=None,
):
    history = history or []

    try:
        provider = get_ai_provider()
    except AIProviderNotConfigured as exc:
        raise AIAnalystUnavailable(
            code=exc.code,
            message=str(exc),
        ) from exc

    context = build_verified_intelligence_context(business)
    evidence = build_context_evidence(context)

    try:
        generated = provider.generate(
            instructions=build_analyst_instructions(context),
            conversation=build_conversation_text(
                question=question,
                history=history,
            ),
        )
    except AIProviderError as exc:
        raise AIAnalystUnavailable(
            code=exc.code,
            message=(
                "Ask StockFlow is temporarily unavailable. "
                "Your business records were not changed."
            ),
        ) from exc

    return {
        "answer": generated["text"],
        "provider": generated["provider"],
        "model": generated["model"],
        "generated_at": timezone.now(),
        "confidence": evidence["overallConfidence"],
        "evidence": evidence,
        "read_only": True,
    }
