import json

from .provider import (
    AIProviderError,
    AIProviderNotConfigured,
    get_ai_provider,
)


REPORT_NARRATIVE_INSTRUCTIONS = """
You are StockFlow's management-report narrator.

Rules:
1. The supplied VERIFIED_REPORT is the only source of business facts.
2. Django already calculated every authoritative figure. Do not recalculate,
   replace, estimate, or silently correct a figure.
3. Never invent causes, products, customers, suppliers, transactions, dates,
   forecasts, or recommendations.
4. Distinguish evidence from cause. If StockFlow does not know why something
   changed, say the available data shows the change but does not prove an
   external cause.
5. Keep the response advisory and read-only. Never claim to have changed any
   StockFlow record.
6. Use Ghana cedi formatting with the ₵ symbol.
7. Return clean plain text only. No Markdown headings, bold markers, tables,
   code fences, or other Markdown syntax.
8. Organize the narrative with these exact plain-text labels:
   What happened:
   Why:
   What needs attention:
   What should I do next:
9. Keep the narrative concise and useful to a Ghanaian micro or small business
   owner or manager.
""".strip()


def generate_report_narrative(report_payload):
    """Generate an optional explanation without blocking report creation."""
    safe_payload = {
        "business": report_payload.get("business"),
        "reportType": report_payload.get("reportType"),
        "title": report_payload.get("title"),
        "period": report_payload.get("period"),
        "confidence": report_payload.get("confidence"),
        "metrics": report_payload.get("metrics"),
        "managementQuestions": report_payload.get("managementQuestions"),
        "sourceSummary": report_payload.get("sourceSummary"),
    }

    try:
        provider = get_ai_provider()
    except AIProviderNotConfigured:
        return {
            "status": "unavailable",
            "narrative": "",
            "provider": "",
            "model": "",
        }

    try:
        result = provider.generate(
            instructions=REPORT_NARRATIVE_INSTRUCTIONS,
            conversation=(
                "VERIFIED_REPORT:\n"
                + json.dumps(
                    safe_payload,
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
            ),
        )
    except AIProviderError:
        return {
            "status": "unavailable",
            "narrative": "",
            "provider": provider.name,
            "model": getattr(provider, "model", ""),
        }

    return {
        "status": "completed",
        "narrative": result["text"],
        "provider": result["provider"],
        "model": result["model"],
    }
