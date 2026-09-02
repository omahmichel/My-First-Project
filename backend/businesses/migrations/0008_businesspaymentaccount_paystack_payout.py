from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("businesses", "0007_business_deals_in"),
    ]

    operations = [
        migrations.AddField(
            model_name="businesspaymentaccount",
            name="paystack_recipient_code",
            field=models.CharField(blank=True, max_length=80),
        ),
        migrations.AddField(
            model_name="businesspaymentaccount",
            name="paystack_recipient_id",
            field=models.CharField(blank=True, max_length=80),
        ),
        migrations.AddField(
            model_name="businesspaymentaccount",
            name="paystack_recipient_last_error",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="businesspaymentaccount",
            name="paystack_recipient_synced_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
