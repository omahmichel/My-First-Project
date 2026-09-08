from datetime import date, datetime, timedelta, timezone as dt_timezone
from decimal import Decimal
from uuid import UUID

from django.db import IntegrityError, transaction
from django.utils import timezone

from inventory.models import Product, StockMovement
from sales.models import Sale

from ..models import AutomationEvent, AutomationRule, AutomationRun
from .business_analysis import (
    RECOGNIZED_SALE_STATUSES,
    calculate_business_overview,
)
from .recommendations import generate_and_store_recommendations
from .reports import generate_and_store_report


RISK_DEFAULTS = {
    "large_discount_percent": 20,
    "stock_adjustment_percent": 25,
    "stock_adjustment_min_units": 5,
    "first_run_lookback_hours": 24,
}

RULE_SCHEDULES = {
    AutomationRule.RuleType.RISK_MONITOR: (
        AutomationRule.ScheduleFrequency.HOURLY
    ),
    AutomationRule.RuleType.DAILY_CLOSING: (
        AutomationRule.ScheduleFrequency.DAILY
    ),
    AutomationRule.RuleType.WEEKLY_MANAGEMENT: (
        AutomationRule.ScheduleFrequency.WEEKLY
    ),
}

RECOMMENDATION_EVENT_TYPES = {
    "restock_stockout_risk": AutomationEvent.EventType.STOCKOUT_RISK,
    "reduce_overstock_exposure": AutomationEvent.EventType.OVERSTOCK,
    "review_margin_deterioration": AutomationEvent.EventType.MARGIN,
    "investigate_sales_anomaly": AutomationEvent.EventType.SALES_ANOMALY,
    "collect_customer_debt": AutomationEvent.EventType.CUSTOMER_DEBT,
    "review_supplier_debt": AutomationEvent.EventType.SUPPLIER_DEBT,
    "review_revenue_decline": AutomationEvent.EventType.REVENUE_DECLINE,
}


class AutomationRuleConflict(Exception):
    pass


def _json_safe(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, dict):
        return {
            str(key): _json_safe(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _rule_config(config=None):
    values = dict(RISK_DEFAULTS)
    if config:
        values.update(config)
    return values


def calculate_next_run(
    *,
    rule_type,
    hour_utc=0,
    weekday=None,
    after=None,
):
    current = (after or timezone.now()).astimezone(dt_timezone.utc)

    if rule_type == AutomationRule.RuleType.RISK_MONITOR:
        return (
            current.replace(
                minute=0,
                second=0,
                microsecond=0,
            )
            + timedelta(hours=1)
        )

    candidate = current.replace(
        hour=int(hour_utc),
        minute=0,
        second=0,
        microsecond=0,
    )

    if rule_type == AutomationRule.RuleType.DAILY_CLOSING:
        if candidate <= current:
            candidate += timedelta(days=1)
        return candidate

    target_weekday = 0 if weekday is None else int(weekday)
    days_ahead = (target_weekday - current.weekday()) % 7
    candidate += timedelta(days=days_ahead)
    if candidate <= current:
        candidate += timedelta(days=7)
    return candidate


def create_automation_rule(*, business, user, data):
    rule_type = data["rule_type"]
    frequency = RULE_SCHEDULES[rule_type]
    hour_utc = int(data.get("hour_utc", 0))
    weekday = data.get("weekday")

    if rule_type == AutomationRule.RuleType.DAILY_CLOSING:
        hour_utc = int(data.get("hour_utc", 18))
        weekday = None
    elif rule_type == AutomationRule.RuleType.WEEKLY_MANAGEMENT:
        hour_utc = int(data.get("hour_utc", 8))
        weekday = int(data.get("weekday", 0))
    else:
        hour_utc = 0
        weekday = None

    is_enabled = data.get("is_enabled", True)
    config = (
        _rule_config(data.get("config"))
        if rule_type == AutomationRule.RuleType.RISK_MONITOR
        else {}
    )

    try:
        return AutomationRule.objects.create(
            business=business,
            created_by=user,
            rule_type=rule_type,
            schedule_frequency=frequency,
            is_enabled=is_enabled,
            hour_utc=hour_utc,
            weekday=weekday,
            include_ai_summary=bool(
                data.get("include_ai_summary", False)
            ),
            config=config,
            next_run_at=(
                calculate_next_run(
                    rule_type=rule_type,
                    hour_utc=hour_utc,
                    weekday=weekday,
                )
                if is_enabled
                else None
            ),
        )
    except IntegrityError as exc:
        raise AutomationRuleConflict(
            "This automation rule already exists for the business."
        ) from exc


def update_automation_rule(*, rule, data):
    was_enabled = rule.is_enabled

    if "is_enabled" in data:
        rule.is_enabled = bool(data["is_enabled"])

    if rule.rule_type == AutomationRule.RuleType.RISK_MONITOR:
        config = dict(rule.config or {})
        config.update(data.get("config") or {})
        rule.config = _rule_config(config)
        rule.hour_utc = 0
        rule.weekday = None
        rule.include_ai_summary = False
    else:
        if "hour_utc" in data:
            rule.hour_utc = int(data["hour_utc"])

        if rule.rule_type == AutomationRule.RuleType.WEEKLY_MANAGEMENT:
            if "weekday" in data:
                rule.weekday = int(data["weekday"])
            elif rule.weekday is None:
                rule.weekday = 0
        else:
            rule.weekday = None

        if "include_ai_summary" in data:
            rule.include_ai_summary = bool(
                data["include_ai_summary"]
            )

    if rule.is_enabled:
        schedule_changed = any(
            key in data
            for key in ("hour_utc", "weekday")
        )
        if not was_enabled or schedule_changed or not rule.next_run_at:
            rule.next_run_at = calculate_next_run(
                rule_type=rule.rule_type,
                hour_utc=rule.hour_utc,
                weekday=rule.weekday,
            )
    else:
        rule.next_run_at = None

    rule.save()
    return rule


def _event(
    *,
    rule,
    event_type,
    severity,
    title,
    summary,
    evidence,
    dedupe_key,
):
    event, created = AutomationEvent.objects.get_or_create(
        business=rule.business,
        dedupe_key=dedupe_key,
        defaults={
            "rule": rule,
            "event_type": event_type,
            "severity": severity,
            "title": title,
            "summary": summary,
            "evidence": _json_safe(evidence),
        },
    )
    return event if created else None


def _daily_key(prefix, subject, now):
    return f"{prefix}:{subject}:{now.date().isoformat()}"


def _recommendation_subject(insight):
    evidence = insight.evidence or {}
    return (
        evidence.get("product_id")
        or evidence.get("signal_type")
        or evidence.get("recommendation_code")
        or insight.title.lower().replace(" ", "-")[:80]
    )


def _recommendation_events(*, rule, now):
    generated = generate_and_store_recommendations(
        rule.business,
        as_of=now,
    )
    events = []

    for insight in generated["recommendations"]:
        evidence = insight.evidence or {}
        code = evidence.get("recommendation_code", "")
        event_type = RECOMMENDATION_EVENT_TYPES.get(
            code,
            AutomationEvent.EventType.RECOMMENDATION,
        )
        subject = _recommendation_subject(insight)
        event = _event(
            rule=rule,
            event_type=event_type,
            severity=insight.severity,
            title=insight.title,
            summary=insight.summary,
            evidence={
                "businessInsightId": str(insight.id),
                "confidence": insight.confidence,
                **evidence,
            },
            dedupe_key=_daily_key(
                f"recommendation:{code or event_type}",
                subject,
                now,
            ),
        )
        if event:
            events.append(event)

    return events


def _overview_events(*, rule, overview, now):
    events = []

    for product in Product.objects.filter(
        business=rule.business,
        is_active=True,
    ).order_by("name"):
        available = max(
            0,
            product.stock - product.reserved_stock,
        )
        if available > product.low_stock_level:
            continue

        severity = (
            AutomationEvent.Severity.HIGH
            if available == 0
            else AutomationEvent.Severity.ATTENTION
        )
        event = _event(
            rule=rule,
            event_type=AutomationEvent.EventType.LOW_STOCK,
            severity=severity,
            title=f"Low stock: {product.name}",
            summary=(
                f"{product.name} has {available} available unit(s) "
                f"against a low-stock level of "
                f"{product.low_stock_level}. Review stock position "
                "before confirming any restock action."
            ),
            evidence={
                "productId": str(product.id),
                "name": product.name,
                "sku": product.sku,
                "availableStock": available,
                "physicalStock": product.stock,
                "reservedStock": product.reserved_stock,
                "lowStockLevel": product.low_stock_level,
            },
            dedupe_key=_daily_key(
                "low-stock",
                product.id,
                now,
            ),
        )
        if event:
            events.append(event)

    products = overview.get("products") or {}
    for candidate in products.get("dead_stock_candidates", []):
        product_id = candidate.get("product_id") or candidate.get("sku")
        event = _event(
            rule=rule,
            event_type=AutomationEvent.EventType.DEAD_STOCK,
            severity=AutomationEvent.Severity.ATTENTION,
            title=f'Dead-stock candidate: {candidate.get("name")}',
            summary=(
                f'{candidate.get("name")} has '
                f'{candidate.get("available_stock", 0)} available '
                "unit(s) and meets StockFlow's verified dead-stock "
                "rule. Review purchasing, pricing or promotion before "
                "adding more stock."
            ),
            evidence=candidate,
            dedupe_key=_daily_key(
                "dead-stock",
                product_id,
                now,
            ),
        )
        if event:
            events.append(event)

    return events


def _window_start(rule, now):
    if rule.last_run_at:
        return rule.last_run_at

    hours = int(
        _rule_config(rule.config).get(
            "first_run_lookback_hours",
            24,
        )
    )
    return now - timedelta(hours=max(1, min(hours, 168)))


def _transaction_events(*, rule, now):
    config = _rule_config(rule.config)
    window_start = _window_start(rule, now)
    events = []

    discount_threshold = Decimal(
        str(config["large_discount_percent"])
    )
    sales = Sale.objects.filter(
        business=rule.business,
        status__in=RECOGNIZED_SALE_STATUSES,
        completed_at__gte=window_start,
        completed_at__lte=now,
        discount__gt=Decimal("0"),
    ).order_by("completed_at")

    for sale in sales:
        if sale.subtotal <= Decimal("0"):
            continue

        percent = (
            sale.discount
            / sale.subtotal
            * Decimal("100")
        ).quantize(Decimal("0.01"))

        if percent < discount_threshold:
            continue

        event = _event(
            rule=rule,
            event_type=AutomationEvent.EventType.LARGE_DISCOUNT,
            severity=AutomationEvent.Severity.ATTENTION,
            title=f"Large discount on {sale.sale_number}",
            summary=(
                f"Sale {sale.sale_number} received a {percent}% "
                f"discount (₵{sale.discount:,.2f}) on a subtotal of "
                f"₵{sale.subtotal:,.2f}. Review the sale record if "
                "this discount was unexpected."
            ),
            evidence={
                "saleId": str(sale.id),
                "saleNumber": sale.sale_number,
                "invoiceNumber": sale.invoice_number,
                "subtotal": str(sale.subtotal),
                "discount": str(sale.discount),
                "discountPercent": str(percent),
                "thresholdPercent": str(discount_threshold),
                "completedAt": sale.completed_at,
            },
            dedupe_key=f"large-discount:{sale.id}",
        )
        if event:
            events.append(event)

    adjustment_percent = Decimal(
        str(config["stock_adjustment_percent"])
    )
    min_units = int(config["stock_adjustment_min_units"])

    movements = StockMovement.objects.filter(
        business=rule.business,
        movement_type=StockMovement.MovementType.ADJUSTMENT,
        created_at__gte=window_start,
        created_at__lte=now,
    ).order_by("created_at")

    for movement in movements:
        absolute_units = abs(movement.quantity)
        base_stock = max(1, movement.previous_stock)
        percent = (
            Decimal(absolute_units)
            / Decimal(base_stock)
            * Decimal("100")
        ).quantize(Decimal("0.01"))

        if (
            absolute_units < min_units
            or percent < adjustment_percent
        ):
            continue

        event = _event(
            rule=rule,
            event_type=AutomationEvent.EventType.STOCK_ADJUSTMENT,
            severity=AutomationEvent.Severity.HIGH,
            title=f"Review stock adjustment: {movement.product_name}",
            summary=(
                f"{movement.product_name} was manually adjusted by "
                f"{movement.quantity:+d} unit(s), moving stock from "
                f"{movement.previous_stock} to {movement.new_stock}. "
                "Review the permanent stock-movement record if this "
                "change was unexpected."
            ),
            evidence={
                "movementId": str(movement.id),
                "productId": str(movement.product_id),
                "productName": movement.product_name,
                "quantity": movement.quantity,
                "previousStock": movement.previous_stock,
                "newStock": movement.new_stock,
                "adjustmentPercent": str(percent),
                "thresholdPercent": str(adjustment_percent),
                "minimumUnits": min_units,
                "reason": movement.reason,
                "createdByName": movement.created_by_name,
                "createdAt": movement.created_at,
            },
            dedupe_key=f"stock-adjustment:{movement.id}",
        )
        if event:
            events.append(event)

    return events


def _run_risk_monitor(*, rule, now):
    overview = calculate_business_overview(
        rule.business,
        as_of=now,
    )

    events = []
    events.extend(_recommendation_events(rule=rule, now=now))
    events.extend(
        _overview_events(
            rule=rule,
            overview=overview,
            now=now,
        )
    )
    events.extend(_transaction_events(rule=rule, now=now))

    return {
        "event_count": len(events),
        "event_ids": [str(event.id) for event in events],
        "action": "advisory_events_only",
        "read_only_transactional_records": True,
    }


def _run_report_rule(*, rule):
    report_type = (
        "daily_summary"
        if rule.rule_type == AutomationRule.RuleType.DAILY_CLOSING
        else "weekly_management"
    )
    report = generate_and_store_report(
        business=rule.business,
        generated_by=None,
        report_type=report_type,
        include_ai_summary=rule.include_ai_summary,
    )

    event = _event(
        rule=rule,
        event_type=AutomationEvent.EventType.REPORT_GENERATED,
        severity=AutomationEvent.Severity.INFO,
        title=f"{report.title} generated",
        summary=(
            f"StockFlow generated the scheduled {report.title}. "
            "Open Intelligence Reports to review the verified figures."
        ),
        evidence={
            "reportId": str(report.id),
            "reportType": report.report_type,
            "dataConfidence": report.data_confidence,
            "aiStatus": report.ai_status,
            "generatedAt": report.generated_at,
        },
        dedupe_key=f"generated-report:{report.id}",
    )

    return {
        "event_count": 1 if event else 0,
        "event_ids": [str(event.id)] if event else [],
        "report_id": str(report.id),
        "report_type": report.report_type,
        "ai_status": report.ai_status,
        "action": "generated_report_only",
        "read_only_transactional_records": True,
    }


def execute_automation_rule(
    rule,
    *,
    trigger_type,
    requested_by=None,
):
    run = AutomationRun.objects.create(
        business=rule.business,
        rule=rule,
        requested_by=requested_by,
        trigger_type=trigger_type,
        status=AutomationRun.Status.RUNNING,
    )
    now = timezone.now()

    try:
        if rule.rule_type == AutomationRule.RuleType.RISK_MONITOR:
            result = _run_risk_monitor(
                rule=rule,
                now=now,
            )
        else:
            result = _run_report_rule(rule=rule)

        finished_at = timezone.now()
        run.status = AutomationRun.Status.COMPLETED
        run.finished_at = finished_at
        run.event_count = int(result.get("event_count", 0))
        run.result = _json_safe(result)
        run.save(
            update_fields=(
                "status",
                "finished_at",
                "event_count",
                "result",
            )
        )

        rule.last_run_at = now
        rule.last_status = AutomationRule.LastStatus.COMPLETED
        rule.last_error = ""
        rule.consecutive_failures = 0
        rule.save(
            update_fields=(
                "last_run_at",
                "last_status",
                "last_error",
                "consecutive_failures",
                "updated_at",
            )
        )
        # External messaging is intentionally downstream of a successful
        # Intelligence run. Messaging failures must never change the verified
        # analytics/automation result or mutate transactional business data.
        try:
            from integrations.messaging.service import dispatch_intelligence_events

            dispatch_intelligence_events(
                business=rule.business,
                rule=rule,
                since=now,
            )
        except Exception:
            pass

        return run
    except Exception as exc:
        finished_at = timezone.now()
        error_code = exc.__class__.__name__[:80]
        safe_error = (
            "Automation execution failed. StockFlow made no "
            "transactional business changes."
        )

        run.status = AutomationRun.Status.FAILED
        run.finished_at = finished_at
        run.error_code = error_code
        run.error_message = safe_error
        run.result = {
            "read_only_transactional_records": True,
        }
        run.save(
            update_fields=(
                "status",
                "finished_at",
                "error_code",
                "error_message",
                "result",
            )
        )

        rule.last_status = AutomationRule.LastStatus.FAILED
        rule.last_error = safe_error
        rule.consecutive_failures += 1
        rule.save(
            update_fields=(
                "last_status",
                "last_error",
                "consecutive_failures",
                "updated_at",
            )
        )
        return run


def process_due_automations(*, limit=50):
    now = timezone.now()
    candidate_ids = list(
        AutomationRule.objects.filter(
            is_enabled=True,
            next_run_at__isnull=False,
            next_run_at__lte=now,
        )
        .order_by("next_run_at")
        .values_list("id", flat=True)[:limit]
    )

    processed = 0
    completed = 0
    failed = 0

    for rule_id in candidate_ids:
        with transaction.atomic():
            rule = (
                AutomationRule.objects.select_for_update()
                .select_related("business")
                .filter(
                    id=rule_id,
                    is_enabled=True,
                )
                .first()
            )
            if (
                not rule
                or not rule.next_run_at
                or rule.next_run_at > timezone.now()
            ):
                continue

            scheduled_for = rule.next_run_at
            rule.next_run_at = calculate_next_run(
                rule_type=rule.rule_type,
                hour_utc=rule.hour_utc,
                weekday=rule.weekday,
                after=max(timezone.now(), scheduled_for),
            )
            rule.save(
                update_fields=("next_run_at", "updated_at")
            )

        run = execute_automation_rule(
            rule,
            trigger_type=AutomationRun.TriggerType.SCHEDULED,
        )
        processed += 1

        if run.status == AutomationRun.Status.COMPLETED:
            completed += 1
        else:
            failed += 1

    return {
        "processed": processed,
        "completed": completed,
        "failed": failed,
    }
