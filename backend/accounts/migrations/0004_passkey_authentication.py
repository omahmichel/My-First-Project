from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_pendingloginchallenge"),
    ]

    operations = [
        migrations.CreateModel(
            name="PasskeyChallenge",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("challenge_token", models.CharField(db_index=True, max_length=64, unique=True)),
                ("purpose", models.CharField(choices=[("registration", "Registration"), ("authentication", "Authentication")], max_length=20)),
                ("challenge", models.BinaryField()),
                ("expires_at", models.DateTimeField(db_index=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="passkey_challenges", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("-created_at",)},
        ),
        migrations.CreateModel(
            name="PasskeyCredential",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("credential_id", models.BinaryField(unique=True)),
                ("public_key", models.BinaryField()),
                ("sign_count", models.PositiveBigIntegerField(default=0)),
                ("transports", models.JSONField(blank=True, default=list)),
                ("device_type", models.CharField(blank=True, max_length=30)),
                ("backed_up", models.BooleanField(default=False)),
                ("label", models.CharField(default="Biometric sign-in", max_length=80)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("last_used_at", models.DateTimeField(blank=True, null=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="passkey_credentials", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("-created_at",)},
        ),
        migrations.AddIndex(
            model_name="passkeycredential",
            index=models.Index(fields=["user", "created_at"], name="accounts_pas_user_id_134a45_idx"),
        ),
    ]
