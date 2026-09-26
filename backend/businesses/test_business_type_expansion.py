from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Business


User = get_user_model()


class BusinessTypeExpansionTests(APITestCase):
    """Protects the five additional StockFlow business routes."""

    NEW_TYPES = (
        Business.BusinessType.PROVISION_MINI_MART,
        Business.BusinessType.PHONE_ELECTRONICS_ACCESSORIES,
        Business.BusinessType.ELECTRICAL_ELECTRONICS,
        Business.BusinessType.AUTO_SPARE_PARTS,
        Business.BusinessType.COSMETICS_BEAUTY,
    )

    def setUp(self):
        self.owner = User.objects.create_user(
            email="routes.owner@stockflow.test",
            password="StrongPass123!",
            full_name="Routes Owner",
        )
        self.client.force_authenticate(user=self.owner)
        self.url = reverse("business-list")

    def test_each_new_business_type_can_be_created_through_api(self):
        for index, business_type in enumerate(self.NEW_TYPES, start=1):
            with self.subTest(business_type=business_type):
                response = self.client.post(
                    self.url,
                    {
                        "name": f"Route Test {index}",
                        "business_type": business_type,
                        "phone": f"02400000{index:02d}",
                        "email": f"route{index}@stockflow.test",
                        "location": "Accra",
                        "dealsIn": ["General products"],
                    },
                    format="json",
                )

                self.assertEqual(
                    response.status_code,
                    status.HTTP_201_CREATED,
                    response.data,
                )
                self.assertEqual(
                    response.data["business_type"],
                    business_type,
                )
                self.assertTrue(
                    Business.objects.filter(
                        pk=response.data["id"],
                        business_type=business_type,
                    ).exists()
                )
