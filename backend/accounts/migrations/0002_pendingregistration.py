from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="PendingRegistration",
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
                ("email", models.EmailField(max_length=254, unique=True)),
                ("full_name", models.CharField(max_length=150)),
                ("phone", models.CharField(blank=True, max_length=30)),
                ("password_hash", models.CharField(max_length=128)),
                ("otp_hash", models.CharField(max_length=128)),
                ("expires_at", models.DateTimeField(db_index=True)),
                ("resend_available_at", models.DateTimeField()),
                (
                    "failed_attempts",
                    models.PositiveSmallIntegerField(default=0),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ("-updated_at",),
            },
        ),
    ]
