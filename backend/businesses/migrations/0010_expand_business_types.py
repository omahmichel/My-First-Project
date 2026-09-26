from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("businesses", "0009_branch_branchaccess_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="business",
            name="business_type",
            field=models.CharField(
                choices=[
                    ("building_materials", "Building materials"),
                    ("boutique", "Boutique"),
                    ("provision_mini_mart", "Provision Shop & Mini Mart"),
                    (
                        "phone_electronics_accessories",
                        "Phone & Electronics Accessories",
                    ),
                    (
                        "electrical_electronics",
                        "Electrical / Electronics Shop",
                    ),
                    ("auto_spare_parts", "Auto Spare Parts"),
                    ("cosmetics_beauty", "Cosmetics & Beauty"),
                ],
                max_length=30,
            ),
        ),
    ]
