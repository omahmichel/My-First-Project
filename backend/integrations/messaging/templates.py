MAX_SMS_LENGTH = 160


def intelligence_event_sms(event):
    """Builds a compact message only from verified stored Intelligence output."""
    title = " ".join(str(event.title or "StockFlow alert").split())
    summary = " ".join(str(event.summary or "").split())
    message = f"StockFlow: {title}."
    if summary:
        message += f" {summary}"
    if len(message) <= MAX_SMS_LENGTH:
        return message
    return message[: MAX_SMS_LENGTH - 3].rstrip() + "..."


def test_sms_message(business):
    name = " ".join(str(business.name or "your business").split())
    message = f"StockFlow SMS test for {name}. Intelligence alerts are connected successfully."
    if len(message) <= MAX_SMS_LENGTH:
        return message
    return message[: MAX_SMS_LENGTH - 3].rstrip() + "..."
