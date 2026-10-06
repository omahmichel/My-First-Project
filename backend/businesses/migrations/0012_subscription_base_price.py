from decimal import Decimal
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("businesses", "0011_subscription_payment_fee")]
    operations = [
        migrations.AlterField(model_name="subscriptionpayment", name="amount", field=models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("150.00"))),
        migrations.AlterField(model_name="subscriptionpayment", name="amount_subunit", field=models.PositiveIntegerField(default=15000)),
    ]
