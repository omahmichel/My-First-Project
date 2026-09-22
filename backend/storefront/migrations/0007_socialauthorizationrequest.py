import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [
        ('storefront', '0006_socialdeliveryattempt_provider_container_id'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [migrations.CreateModel(name='SocialAuthorizationRequest', fields=[
        ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
        ('provider', models.CharField(max_length=20)),
        ('nonce', models.CharField(max_length=100)),
        ('expires_at', models.DateTimeField(db_index=True)),
        ('received', models.BooleanField(default=False)),
        ('consumed', models.BooleanField(default=False)),
        ('encrypted_code', models.TextField(blank=True)),
        ('business', models.ForeignKey(to='businesses.business', on_delete=django.db.models.deletion.CASCADE)),
        ('user', models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.CASCADE)),
    ])]
