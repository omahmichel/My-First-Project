import requests
from django.conf import settings


class AIProviderError(Exception):
    code = "ai_provider_unavailable"


class AIProviderNotConfigured(AIProviderError):
    code = "ai_not_configured"


def _extract_output_text(payload):
    direct = payload.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()

    chunks = []
    for item in payload.get("output", []):
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []):
            if not isinstance(content, dict):
                continue
            text = content.get("text")
            if isinstance(text, str) and text.strip():
                chunks.append(text.strip())

    text = "\n".join(chunks).strip()
    if not text:
        raise AIProviderError(
            "The AI provider returned no usable answer."
        )
    return text


class OpenAIResponsesProvider:
    name = "openai"

    def __init__(self):
        self.api_key = settings.STOCKFLOW_AI_API_KEY
        self.model = settings.STOCKFLOW_AI_MODEL
        self.api_url = settings.STOCKFLOW_AI_API_URL
        self.timeout_seconds = settings.STOCKFLOW_AI_TIMEOUT_SECONDS
        self.max_output_tokens = settings.STOCKFLOW_AI_MAX_OUTPUT_TOKENS

        if not self.api_key:
            raise AIProviderNotConfigured(
                "Ask StockFlow is not configured yet."
            )
        if not self.model:
            raise AIProviderNotConfigured(
                "Ask StockFlow does not have an AI model configured."
            )

    def generate(self, *, instructions, conversation):
        try:
            response = requests.post(
                self.api_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "instructions": instructions,
                    "input": conversation,
                    "max_output_tokens": self.max_output_tokens,
                },
                timeout=self.timeout_seconds,
            )
        except requests.RequestException as exc:
            raise AIProviderError(
                "Ask StockFlow could not reach the AI provider."
            ) from exc

        if response.status_code >= 400:
            raise AIProviderError(
                "Ask StockFlow could not complete the AI request."
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise AIProviderError(
                "The AI provider returned an invalid response."
            ) from exc

        return {
            "text": _extract_output_text(payload),
            "provider": self.name,
            "model": self.model,
        }


def get_ai_provider():
    provider_name = settings.STOCKFLOW_AI_PROVIDER

    if provider_name == "openai":
        return OpenAIResponsesProvider()

    if not provider_name:
        raise AIProviderNotConfigured(
            "Ask StockFlow is not configured yet."
        )

    raise AIProviderNotConfigured(
        "The configured StockFlow AI provider is not supported."
    )
