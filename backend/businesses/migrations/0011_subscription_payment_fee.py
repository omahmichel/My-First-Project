from decimal import Decimal
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("businesses", "0010_expand_business_types")]
    operations = [
        migrations.AddField(model_name="subscriptionpayment", name="fee_percent", field=models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))),
        migrations.AddField(model_name="subscriptionpayment", name="fee_amount", field=models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))),
    ]
