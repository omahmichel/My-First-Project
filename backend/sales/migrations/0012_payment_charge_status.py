from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("sales", "0011_paystack_mode")]
    operations = [migrations.AddField(
        model_name="payment", name="gateway_charge_status",
        field=models.CharField(max_length=32, blank=True, default=""),
    )]
