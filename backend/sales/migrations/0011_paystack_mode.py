from django.db import migrations, models
class Migration(migrations.Migration):
    dependencies = [("sales", "0010_payment_fee")]
    operations = [migrations.AddField(model_name="payment", name="gateway_mode", field=models.CharField(max_length=4, blank=True, default=""))]
