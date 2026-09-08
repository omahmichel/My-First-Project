from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from businesses.models import Branch, Business, BusinessMembership
from integrations.models import ExternalCommerceOrder
from inventory.models import Product
from inventory.restock_models import RestockPurchase, Supplier


class EcommerceSupplierOrderIntegrationTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(
            email="slice4-owner@example.com",
            password="StrongPass123!",
        )
        self.manager = User.objects.create_user(
            email="slice4-manager@example.com",
            password="StrongPass123!",
        )
        self.cashier = User.objects.create_user(
            email="slice4-cashier@example.com",
            password="StrongPass123!",
        )
        self.business = Business.objects.create(
            owner=self.owner,
            name="Slice Four Business",
            slug="slice-four-business",
            business_type=Business.BusinessType.BUILDING_MATERIALS,
        )
        BusinessMembership.objects.create(
            business=self.business,
            user=self.manager,
            role=BusinessMembership.Role.MANAGER,
        )
        BusinessMembership.objects.create(
            business=self.business,
            user=self.cashier,
            role=BusinessMembership.Role.CASHIER,
        )
        self.branch = Branch.objects.create(
            business=self.business,
            name="Main Branch",
            code="MAIN",
            is_main=True,
            is_active=True,
            created_by=self.owner,
        )
        self.product = Product.objects.create(
            business=self.business,
            name="Connector Cement",
            sku="CON-CEM-001",
            category="Cement",
            unit=Product.Unit.BAG,
            stock=0,
            cost_price=Decimal("0.00"),
            selling_price=Decimal("50.00"),
            is_active=True,
        )
        self.supplier = Supplier.objects.create(
            business=self.business,
            name="Connector Supplier",
            phone="0244000099",
            is_active=True,
        )

    def commerce_base(self):
        return f"/api/businesses/{self.business.id}/integrations/commerce"

    def supplier_base(self):
        return f"/api/businesses/{self.business.id}/integrations/supplier-orders"

    def create_connection(self):
        self.client.force_authenticate(self.owner)
        response = self.client.post(
            self.commerce_base() + "/connections/",
            {
                "provider": "shopify",
                "name": "Main Store",
                "shopUrl": "https://example-shop.myshopify.com",
                "settings": {"catalogMode": "stockflow"},
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        return response.data

    def test_commerce_capabilities_are_safe_and_provider_neutral(self):
        self.client.force_authenticate(self.owner)
        response = self.client.get(self.commerce_base() + "/capabilities/")
        self.assertEqual(response.status_code, 200)
        providers = {row["provider"]: row for row in response.data["providers"]}
        self.assertIn("shopify", providers)
        self.assertIn("woocommerce", providers)
        self.assertFalse(providers["shopify"]["liveConnectionAvailable"])
        self.assertFalse(
            response.data["safety"]["externalPlatformMayOverwriteStockFlowInventory"]
        )

    def test_commerce_connection_rejects_provider_secrets(self):
        self.client.force_authenticate(self.owner)
        response = self.client.post(
            self.commerce_base() + "/connections/",
            {
                "provider": "woocommerce",
                "name": "Unsafe Store",
                "shopUrl": "https://shop.example.com",
                "settings": {"nested": {"consumer_secret": "do-not-store-me"}},
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_manager_cannot_manage_commerce_connections(self):
        self.client.force_authenticate(self.manager)
        response = self.client.post(
            self.commerce_base() + "/connections/",
            {"provider": "shopify", "name": "Denied", "settings": {}},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_external_order_staging_is_idempotent_and_never_changes_stock(self):
        connection = self.create_connection()
        mapping = self.client.post(
            self.commerce_base()
            + f"/connections/{connection['id']}/product-mappings/",
            {
                "externalProductId": "shop-product-1",
                "productId": str(self.product.id),
            },
            format="json",
        )
        self.assertEqual(mapping.status_code, 201)

        self.client.force_authenticate(self.manager)
        payload = {
            "connectionId": connection["id"],
            "externalOrderId": "shop-order-1001",
            "externalOrderNumber": "#1001",
            "paymentStatus": "paid",
            "currency": "GHS",
            "customerName": "External Buyer",
            "subtotal": "100.00",
            "discount": "0.00",
            "shippingTotal": "0.00",
            "total": "100.00",
            "items": [
                {
                    "externalItemId": "line-1",
                    "externalProductId": "shop-product-1",
                    "name": "Connector Cement",
                    "sku": "CON-CEM-001",
                    "quantity": 2,
                    "unitPrice": "50.00",
                }
            ],
        }
        first = self.client.post(
            self.commerce_base() + "/orders/stage/",
            payload,
            format="json",
        )
        self.assertEqual(first.status_code, 201)
        self.assertEqual(first.data["status"], "ready")
        self.assertFalse(first.data["stockMutation"])
        self.assertFalse(first.data["saleCreation"])
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 0)

        replay = self.client.post(
            self.commerce_base() + "/orders/stage/",
            payload,
            format="json",
        )
        self.assertEqual(replay.status_code, 200)
        self.assertTrue(replay.data["idempotentReplay"])
        self.assertEqual(ExternalCommerceOrder.objects.count(), 1)

        conflicting = dict(payload)
        conflicting["subtotal"] = "150.00"
        conflicting["total"] = "150.00"
        conflicting["items"] = [{**payload["items"][0], "quantity": 3}]
        conflict = self.client.post(
            self.commerce_base() + "/orders/stage/",
            conflicting,
            format="json",
        )
        self.assertEqual(conflict.status_code, 400)

    def test_unmapped_external_order_is_blocked_without_stock_mutation(self):
        connection = self.create_connection()
        self.client.force_authenticate(self.manager)
        response = self.client.post(
            self.commerce_base() + "/orders/stage/",
            {
                "connectionId": connection["id"],
                "externalOrderId": "unmapped-1",
                "subtotal": "20.00",
                "total": "20.00",
                "items": [
                    {
                        "externalItemId": "line-u1",
                        "externalProductId": "unknown-product",
                        "name": "Unknown",
                        "quantity": 1,
                        "unitPrice": "20.00",
                    }
                ],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], "blocked")
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 0)

    def create_po(self):
        self.client.force_authenticate(self.manager)
        response = self.client.post(
            self.supplier_base() + "/",
            {
                "branchId": str(self.branch.id),
                "supplierId": str(self.supplier.id),
                "supplierReference": "SUP-PO-001",
                "items": [
                    {
                        "productId": str(self.product.id),
                        "quantity": 10,
                        "unitCost": "20.00",
                    }
                ],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        return response.data

    def test_supplier_po_does_not_change_stock_until_received(self):
        purchase_order = self.create_po()
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 0)
        self.assertEqual(purchase_order["status"], "draft")
        self.assertEqual(RestockPurchase.objects.count(), 0)

    def test_supplier_po_partial_receive_reuses_restock_and_is_idempotent(self):
        purchase_order = self.create_po()
        issue = self.client.post(
            self.supplier_base() + f"/{purchase_order['id']}/issue/",
            {},
            format="json",
        )
        self.assertEqual(issue.status_code, 200)
        item_id = issue.data["items"][0]["id"]

        receipt_payload = {
            "idempotencyKey": "spo-receipt-001",
            "initialPayment": "0.00",
            "items": [
                {"purchaseOrderItemId": item_id, "quantity": 4}
            ],
        }
        first = self.client.post(
            self.supplier_base() + f"/{purchase_order['id']}/receive/",
            receipt_payload,
            format="json",
        )
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.data["purchaseOrder"]["status"], "partially_received")
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 4)
        self.assertEqual(RestockPurchase.objects.count(), 1)

        replay = self.client.post(
            self.supplier_base() + f"/{purchase_order['id']}/receive/",
            receipt_payload,
            format="json",
        )
        self.assertEqual(replay.status_code, 200)
        self.assertTrue(replay.data["idempotentReplay"])
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 4)
        self.assertEqual(RestockPurchase.objects.count(), 1)

        second = self.client.post(
            self.supplier_base() + f"/{purchase_order['id']}/receive/",
            {
                "idempotencyKey": "spo-receipt-002",
                "items": [
                    {"purchaseOrderItemId": item_id, "quantity": 6}
                ],
            },
            format="json",
        )
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.data["purchaseOrder"]["status"], "received")
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 10)
        self.assertEqual(RestockPurchase.objects.count(), 2)

    def test_supplier_po_over_receive_is_rejected_without_stock_change(self):
        purchase_order = self.create_po()
        issue = self.client.post(
            self.supplier_base() + f"/{purchase_order['id']}/issue/",
            {},
            format="json",
        )
        item_id = issue.data["items"][0]["id"]
        response = self.client.post(
            self.supplier_base() + f"/{purchase_order['id']}/receive/",
            {
                "idempotencyKey": "spo-over-receive",
                "items": [
                    {"purchaseOrderItemId": item_id, "quantity": 11}
                ],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 0)
        self.assertEqual(RestockPurchase.objects.count(), 0)

    def test_cashier_cannot_manage_supplier_purchase_orders(self):
        self.client.force_authenticate(self.cashier)
        response = self.client.get(self.supplier_base() + "/")
        self.assertEqual(response.status_code, 403)
