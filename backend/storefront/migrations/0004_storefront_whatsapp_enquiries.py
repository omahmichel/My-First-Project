from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("storefront", "0003_socialchannel_socialpublishingjob_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="storefront",
            name="whatsapp_enabled",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="storefront",
            name="whatsapp_phone",
            field=models.CharField(blank=True, max_length=30),
        ),
    ]
