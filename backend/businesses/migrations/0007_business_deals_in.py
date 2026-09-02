from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("businesses", "0006_business_payment_accounts"),
    ]

    operations = [
        migrations.AddField(
            model_name="business",
            name="deals_in",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
