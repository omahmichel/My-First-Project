from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0007_productvideo"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="retail_details",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
