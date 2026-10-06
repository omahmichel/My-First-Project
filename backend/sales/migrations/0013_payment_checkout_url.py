from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("sales", "0012_payment_charge_status")]
    operations = [migrations.AddField(model_name="payment", name="checkout_url", field=models.URLField(max_length=500, blank=True, default=""))]
