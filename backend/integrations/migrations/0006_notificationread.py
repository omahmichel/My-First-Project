from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("integrations", "0005_live_provider_credentials"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [migrations.CreateModel(
        name="NotificationRead",
        fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("notification_key", models.CharField(max_length=180)),
            ("read_at", models.DateTimeField(auto_now_add=True)),
            ("business", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="businesses.business")),
            ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
        ],
        options={"constraints": [models.UniqueConstraint(fields=("business", "user", "notification_key"), name="unique_notification_read_per_user")]},
    )]
