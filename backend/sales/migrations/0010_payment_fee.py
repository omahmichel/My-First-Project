from decimal import Decimal
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("sales", "0009_sale_branch_sale_sales_sale_busines_f62354_idx")]
    operations = [
        migrations.AddField(model_name="payment", name="fee_percent", field=models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))),
        migrations.AddField(model_name="payment", name="fee_amount", field=models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))),
    ]
