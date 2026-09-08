from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("businesses", "0009_branch_branchaccess_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="DataImport",
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
                    "dataset",
                    models.CharField(
                        choices=[
                            ("products", "Products"),
                            ("customers", "Customers"),
                            ("suppliers", "Suppliers"),
                            ("branch_inventory", "Branch inventory"),
                        ],
                        max_length=30,
                    ),
                ),
                (
                    "file_type",
                    models.CharField(
                        choices=[
                            ("csv", "CSV"),
                            ("xlsx", "Excel workbook"),
                        ],
                        max_length=10,
                    ),
                ),
                ("original_filename", models.CharField(max_length=255)),
                ("file_sha256", models.CharField(max_length=64)),
                ("branch_id_snapshot", models.UUIDField(blank=True, null=True)),
                ("branch_name_snapshot", models.CharField(blank=True, max_length=180)),
                ("branch_code_snapshot", models.CharField(blank=True, max_length=40)),
                ("header_mapping", models.JSONField(blank=True, default=dict)),
                ("row_count", models.PositiveIntegerField(default=0)),
                ("valid_count", models.PositiveIntegerField(default=0)),
                ("error_count", models.PositiveIntegerField(default=0)),
                ("create_count", models.PositiveIntegerField(default=0)),
                ("update_count", models.PositiveIntegerField(default=0)),
                ("skip_count", models.PositiveIntegerField(default=0)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("previewed", "Previewed"),
                            ("applied", "Applied"),
                        ],
                        default="previewed",
                        max_length=20,
                    ),
                ),
                ("applied_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "applied_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="applied_data_imports",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "business",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="data_imports",
                        to="businesses.business",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_data_imports",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ("-created_at",)},
        ),
        migrations.AddIndex(
            model_name="dataimport",
            index=models.Index(
                fields=["business", "created_at"],
                name="integration_busines_f98dc0_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="dataimport",
            index=models.Index(
                fields=["business", "status"],
                name="integration_busines_a9aa6f_idx",
            ),
        ),
    ]
