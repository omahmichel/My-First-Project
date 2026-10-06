from django.db import migrations, models
class Migration(migrations.Migration):
    dependencies = [("businesses", "0012_subscription_base_price")]
    operations = [
        migrations.AddField(model_name="businesspaymentaccount", name="paystack_recipient_mode", field=models.CharField(max_length=4, blank=True, default="")),
        migrations.AddField(model_name="subscriptionpayment", name="gateway_mode", field=models.CharField(max_length=4, blank=True, default="")),
    ]
