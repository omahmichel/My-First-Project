from django.test import TestCase, override_settings

from . import test_listings


@override_settings(ALLOWED_HOSTS=["testserver", "localhost"])
class WhatsAppStorefrontTests(TestCase):
    def setUp(self):
        test_listings.ShopListingApiTests.setUp(self)
        self.settings_url = f"/api/businesses/{self.business.id}/storefront/settings/"
        self.public_url = f"/api/shops/{self.business.slug}/"

    def test_whatsapp_enquiries_default_off(self):
        response = self.client.get(self.settings_url)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["whatsappEnabled"])
        self.assertEqual(response.data["whatsappPhone"], "")

    def test_enabling_requires_a_whatsapp_number(self):
        response = self.client.patch(
            self.settings_url,
            {"whatsappEnabled": True},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_owner_can_enable_whatsapp_enquiries_for_public_shop(self):
        response = self.client.patch(
            self.settings_url,
            {"whatsappEnabled": True, "whatsappPhone": "0542777495"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["whatsappEnabled"])
        self.assertEqual(response.data["whatsappPhone"], "0542777495")

        self.shop.refresh_from_db()
        self.shop.is_published = True
        self.shop.save()

        public = self.client.get(self.public_url)
        self.assertEqual(public.status_code, 200)
        self.assertTrue(public.data["shop"]["whatsappEnabled"])
        self.assertEqual(public.data["shop"]["whatsappPhone"], "0542777495")

    def test_disabled_whatsapp_number_is_not_public(self):
        response = self.client.patch(
            self.settings_url,
            {"whatsappEnabled": False, "whatsappPhone": "0542777495"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)

        self.shop.refresh_from_db()
        self.shop.is_published = True
        self.shop.save()

        public = self.client.get(self.public_url)
        self.assertEqual(public.status_code, 200)
        self.assertFalse(public.data["shop"]["whatsappEnabled"])
        self.assertEqual(public.data["shop"]["whatsappPhone"], "")
