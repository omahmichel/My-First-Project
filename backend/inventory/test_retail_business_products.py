from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from businesses.models import Business

from .models import Product


User = get_user_model()


class RetailBusinessProductCompatibilityTests(TestCase):
    """Keeps new retail routes on shared STANDARD products."""

    NEW_TYPES = (
        Business.BusinessType.PROVISION_MINI_MART,
        Business.BusinessType.PHONE_ELECTRONICS_ACCESSORIES,
        Business.BusinessType.ELECTRICAL_ELECTRONICS,
        Business.BusinessType.AUTO_SPARE_PARTS,
        Business.BusinessType.COSMETICS_BEAUTY,
    )

    def setUp(self):
        self.owner = User.objects.create_user(
            email="retail.products@stockflow.test",
            password="StrongPass123!",
            full_name="Retail Product Owner",
        )

    def create_business(self, business_type, index):
        return Business.objects.create(
            owner=self.owner,
            name=f"Retail Route {index}",
            slug=f"retail-route-{index}",
            business_type=business_type,
        )

    def test_standard_product_is_valid_for_each_new_business_type(self):
        for index, business_type in enumerate(self.NEW_TYPES, start=1):
            with self.subTest(business_type=business_type):
                business = self.create_business(business_type, index)
                product = Product(
                    business=business,
                    product_type=Product.ProductType.STANDARD,
                    name=f"Retail Product {index}",
                    sku=f"RTL-{index:03d}",
                    category="General",
                    stock=5,
                )

                product.full_clean()
                product.save()

                self.assertEqual(product.business_id, business.id)

    def test_tile_and_fashion_types_remain_specialist_only(self):
        for index, business_type in enumerate(self.NEW_TYPES, start=20):
            with self.subTest(business_type=business_type):
                business = self.create_business(business_type, index)

                tile = Product(
                    business=business,
                    product_type=Product.ProductType.TILE,
                    name="Wrong Tile",
                    sku=f"TILE-{index}",
                    category="Tiles",
                    design_code="T-001",
                )
                with self.assertRaises(ValidationError):
                    tile.full_clean()

                fashion = Product(
                    business=business,
                    product_type=Product.ProductType.FASHION,
                    name="Wrong Fashion",
                    sku=f"FASHION-{index}",
                    category="Fashion",
                )
                with self.assertRaises(ValidationError):
                    fashion.full_clean()
