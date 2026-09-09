import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("integrations", "0004_ecommerce_supplier_orders"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProviderCredential",
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
                    "category",
                    models.CharField(
                        choices=[
                            ("accounting", "Accounting"),
                            ("commerce", "Commerce"),
                            ("messaging", "Messaging"),
                        ],
                        max_length=20,
                    ),
                ),
                ("provider", models.CharField(max_length=40)),
                ("connection_key", models.CharField(max_length=80)),
                ("encrypted_payload", models.TextField()),
                ("access_expires_at", models.DateTimeField(blank=True, null=True)),
                ("refresh_expires_at", models.DateTimeField(blank=True, null=True)),
                ("last_used_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "business",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="provider_credentials",
                        to="businesses.business",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_provider_credentials",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ("category", "provider", "created_at")},
        ),
        migrations.AddConstraint(
            model_name="providercredential",
            constraint=models.UniqueConstraint(
                fields=("business", "category", "provider", "connection_key"),
                name="uniq_integ_provider_credential",
            ),
        ),
        migrations.AddIndex(
            model_name="providercredential",
            index=models.Index(
                fields=["business", "category", "provider"],
                name="integ_provider_cred_idx",
            ),
        ),
    ]
