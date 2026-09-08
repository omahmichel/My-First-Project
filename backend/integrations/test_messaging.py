from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APITestCase

from businesses.models import Business, BusinessMembership
from integrations.messaging.provider import MessagingProviderError
from integrations.messaging.service import dispatch_intelligence_events
from integrations.models import MessageDelivery, MessagingPreference
from intelligence.models import AutomationEvent, AutomationRule
from intelligence.services.automation import execute_automation_rule


@override_settings(
    MNOTIFY_API_URL="https://api.mnotify.test/api/sms/quick",
    MNOTIFY_API_KEY="test-key",
    MNOTIFY_SENDER_ID="StockFlow",
)
class IntelligenceMessagingTests(APITestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(
            email="messaging-owner@example.com",
            password="StrongPass123!",
        )
        self.manager = user_model.objects.create_user(
            email="messaging-manager@example.com",
            password="StrongPass123!",
        )
        self.business = Business.objects.create(
            owner=self.owner,
            name="Messaging Business",
            slug="messaging-business",
            business_type=Business.BusinessType.BUILDING_MATERIALS,
        )
        BusinessMembership.objects.create(
            business=self.business,
            user=self.manager,
            role=BusinessMembership.Role.MANAGER,
        )
        self.preference_url = (
            f"/api/businesses/{self.business.id}/integrations/messaging/preferences/"
        )

    def preference(self, **overrides):
        values = {
            "sms_enabled": True,
            "recipient_phone": "0244000000",
            "minimum_severity": MessagingPreference.MinimumSeverity.ATTENTION,
        }
        values.update(overrides)
        preference, _ = MessagingPreference.objects.update_or_create(
            business=self.business,
            defaults=values,
        )
        return preference

    def event(self, **overrides):
        values = {
            "business": self.business,
            "event_type": AutomationEvent.EventType.LOW_STOCK,
            "severity": AutomationEvent.Severity.ATTENTION,
            "title": "Low stock: Cement",
            "summary": "Cement has 2 available units. Review stock position.",
            "evidence": {"productId": "example"},
            "dedupe_key": "messaging-test-event",
        }
        values.update(overrides)
        return AutomationEvent.objects.create(**values)

    def test_owner_can_read_and_update_sms_preferences(self):
        self.client.force_authenticate(self.owner)
        response = self.client.get(self.preference_url)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["smsEnabled"])

        updated = self.client.patch(
            self.preference_url,
            {
                "smsEnabled": True,
                "recipientPhone": "0244000000",
                "minimumSeverity": "high",
                "eventTypes": ["low_stock", "stockout_risk"],
            },
            format="json",
        )
        self.assertEqual(updated.status_code, 200)
        self.assertTrue(updated.data["smsEnabled"])
        self.assertEqual(updated.data["minimumSeverity"], "high")

    def test_whatsapp_cannot_be_enabled_before_live_provider_exists(self):
        self.client.force_authenticate(self.owner)
        response = self.client.patch(
            self.preference_url,
            {"whatsappEnabled": True},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("whatsappEnabled", response.data)

    def test_manager_cannot_change_messaging_preferences(self):
        self.client.force_authenticate(self.manager)
        response = self.client.patch(
            self.preference_url,
            {"smsEnabled": False},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    @patch("integrations.messaging.service.MNotifySmsProvider.send")
    def test_intelligence_event_sends_once_and_is_deduplicated(self, send):
        send.return_value = {
            "provider": "mnotify",
            "provider_reference": "message-001",
            "provider_response_summary": "success",
        }
        self.preference()
        event = self.event()

        first = dispatch_intelligence_events(business=self.business)
        second = dispatch_intelligence_events(business=self.business)

        self.assertEqual(first["sent"], 1)
        self.assertEqual(second["created"], 0)
        self.assertEqual(send.call_count, 1)
        delivery = MessageDelivery.objects.get(source_id=str(event.id))
        self.assertEqual(delivery.status, MessageDelivery.Status.SENT)
        self.assertEqual(delivery.provider_reference, "message-001")
        self.assertLessEqual(len(delivery.message), 160)

    @patch("integrations.messaging.service.MNotifySmsProvider.send")
    def test_severity_and_event_filters_prevent_unwanted_sms(self, send):
        self.preference(
            minimum_severity=MessagingPreference.MinimumSeverity.HIGH,
            event_types=[AutomationEvent.EventType.STOCKOUT_RISK],
        )
        self.event()
        summary = dispatch_intelligence_events(business=self.business)
        self.assertEqual(summary["eligible"], 0)
        self.assertEqual(MessageDelivery.objects.count(), 0)
        send.assert_not_called()

    @patch("integrations.messaging.service.MNotifySmsProvider.send")
    def test_provider_failure_is_audited_without_raising(self, send):
        send.side_effect = MessagingProviderError(
            "The SMS provider could not be reached.",
            response_summary="safe-provider-summary",
        )
        self.preference()
        event = self.event(dedupe_key="messaging-provider-failure")
        summary = dispatch_intelligence_events(business=self.business)
        self.assertEqual(summary["failed"], 1)
        delivery = MessageDelivery.objects.get(source_id=str(event.id))
        self.assertEqual(delivery.status, MessageDelivery.Status.FAILED)
        self.assertEqual(delivery.attempt_count, 1)
        self.assertEqual(
            delivery.provider_response_summary,
            "safe-provider-summary",
        )

    @patch("integrations.messaging.service.dispatch_intelligence_events")
    def test_successful_automation_invokes_messaging_after_run(self, dispatch):
        dispatch.return_value = {"eligible": 0, "created": 0, "sent": 0, "failed": 0}
        rule = AutomationRule.objects.create(
            business=self.business,
            created_by=self.owner,
            rule_type=AutomationRule.RuleType.RISK_MONITOR,
            schedule_frequency=AutomationRule.ScheduleFrequency.HOURLY,
            is_enabled=True,
            config={},
        )
        run = execute_automation_rule(
            rule,
            trigger_type="manual",
            requested_by=self.owner,
        )
        self.assertEqual(run.status, "completed")
        dispatch.assert_called_once()
        kwargs = dispatch.call_args.kwargs
        self.assertEqual(kwargs["business"], self.business)
        self.assertEqual(kwargs["rule"], rule)
