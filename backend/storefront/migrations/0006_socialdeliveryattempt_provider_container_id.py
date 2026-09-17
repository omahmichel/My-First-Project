from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('storefront', '0005_socialdeliveryattempt'),
    ]

    operations = [
        migrations.AddField(
            model_name='socialdeliveryattempt',
            name='provider_container_id',
            field=models.CharField(blank=True, max_length=180),
        ),
    ]
