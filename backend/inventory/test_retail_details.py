from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from businesses.models import Business


class RetailDetailsAPITests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="retail.details@stockflow.test",
            password="StrongPass123!",
            full_name="Retail Details Owner",
        )
        self.business = Business.objects.create(
            owner=self.owner,
            name="Auto Parts Test",
            slug="auto-parts-details-test",
            business_type=Business.BusinessType.AUTO_SPARE_PARTS,
        )
        self.client.force_authenticate(user=self.owner)
        self.url = f"/api/businesses/{self.business.id}/products/"

    def test_retail_details_round_trip_through_product_api(self):
        response = self.client.post(
            self.url,
            {
                "productType": "standard",
                "name": "Toyota Oil Filter",
                "sku": "90915-YZZD2",
                "category": "Oil Filters",
                "brand": "Toyota",
                "unit": "piece",
                "stock": 12,
                "lowStockLevel": 3,
                "costPrice": "35.00",
                "sellingPrice": "48.00",
                "retailDetails": {
                    "oemNumber": "90915-YZZD2",
                    "vehicleMake": "Toyota",
                    "vehicleModel": "Corolla",
                    "yearRange": "2008-2018",
                },
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["retailDetails"]["vehicleMake"], "Toyota")
        self.assertEqual(response.data["retailDetails"]["vehicleModel"], "Corolla")

        product_id = response.data["id"]
        update = self.client.patch(
            f"{self.url}{product_id}/",
            {
                "retailDetails": {
                    **response.data["retailDetails"],
                    "engineType": "1.8L petrol",
                }
            },
            format="json",
        )

        self.assertEqual(update.status_code, status.HTTP_200_OK, update.data)
        self.assertEqual(update.data["retailDetails"]["engineType"], "1.8L petrol")
