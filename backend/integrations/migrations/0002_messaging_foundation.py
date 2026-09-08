import uuid

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("integrations", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="MessagingPreference",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("sms_enabled", models.BooleanField(default=False)),
                ("whatsapp_enabled", models.BooleanField(default=False)),
                ("recipient_phone", models.CharField(blank=True, max_length=30)),
                (
                    "minimum_severity",
                    models.CharField(
                        choices=[
                            ("info", "Information and above"),
                            ("attention", "Needs attention and above"),
                            ("high", "High priority only"),
                        ],
                        default="attention",
                        max_length=20,
                    ),
                ),
                ("event_types", models.JSONField(blank=True, default=list)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "business",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="messaging_preference",
                        to="businesses.business",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="MessageDelivery",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "channel",
                    models.CharField(
                        choices=[("sms", "SMS"), ("whatsapp", "WhatsApp")],
                        max_length=20,
                    ),
                ),
                ("message_type", models.CharField(blank=True, max_length=40)),
                ("source_type", models.CharField(blank=True, max_length=40)),
                ("source_id", models.CharField(blank=True, max_length=64)),
                ("dedupe_key", models.CharField(max_length=255, unique=True)),
                ("recipient", models.CharField(max_length=30)),
                ("message", models.TextField()),
                ("provider", models.CharField(blank=True, max_length=40)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("sent", "Sent"),
                            ("failed", "Failed"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("provider_reference", models.CharField(blank=True, max_length=120)),
                ("provider_response_summary", models.TextField(blank=True)),
                ("failure_reason", models.CharField(blank=True, max_length=255)),
                ("attempt_count", models.PositiveIntegerField(default=0)),
                ("sent_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "business",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="message_deliveries",
                        to="businesses.business",
                    ),
                ),
            ],
            options={"ordering": ("-created_at",)},
        ),
        migrations.AddIndex(
            model_name="messagedelivery",
            index=models.Index(
                fields=["business", "created_at"],
                name="integ_msg_bus_created_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="messagedelivery",
            index=models.Index(
                fields=["business", "status"],
                name="integ_msg_bus_status_idx",
            ),
        ),
    ]
