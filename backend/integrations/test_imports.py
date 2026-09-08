import io
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APITestCase

from businesses.models import Branch, Business, BusinessMembership
from customers.models import Customer
from integrations.models import DataImport
from inventory.models import BranchInventory, BranchStockMovement, Product, StockMovement
from inventory.restock_models import Supplier


class SafeDataImportTests(APITestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(
            email="import-owner@example.com",
            password="StrongPass123!",
        )
        self.manager = user_model.objects.create_user(
            email="import-manager@example.com",
            password="StrongPass123!",
        )
        self.business = Business.objects.create(
            owner=self.owner,
            name="Safe Import Business",
            slug="safe-import-business",
            business_type=Business.BusinessType.BUILDING_MATERIALS,
        )
        BusinessMembership.objects.create(
            business=self.business,
            user=self.manager,
            role=BusinessMembership.Role.MANAGER,
        )
        self.branch = Branch.objects.create(
            business=self.business,
            name="Main Branch",
            code="MAIN",
            is_main=True,
            created_by=self.owner,
        )
        self.preview_url = (
            f"/api/businesses/{self.business.id}/integrations/imports/preview/"
        )

    def csv_file(self, name, text):
        return SimpleUploadedFile(
            name,
            text.encode("utf-8"),
            content_type="text/csv",
        )

    def preview(self, dataset, upload, branch=True):
        payload = {"dataset": dataset, "file": upload}
        if branch:
            payload["branchId"] = str(self.branch.id)
        return self.client.post(self.preview_url, payload, format="multipart")

    def apply(self, preview_response):
        import_id = preview_response.data["import"]["id"]
        return self.client.post(
            f"/api/businesses/{self.business.id}/integrations/imports/{import_id}/apply/",
            {"previewToken": preview_response.data["previewToken"]},
            format="json",
        )

    def test_product_preview_is_read_only_then_apply_creates_branch_audit(self):
        self.client.force_authenticate(self.owner)
        upload = self.csv_file(
            "products.csv",
            "Product Name,SKU,Category,Unit,Opening Stock,Cost Price,Selling Price\n"
            "Imported Cement,CEM-900,Cement,bag,12,35.50,50.00\n",
        )
        preview = self.preview("products", upload)
        self.assertEqual(preview.status_code, 201)
        self.assertEqual(preview.data["rows"][0]["action"], "CREATE")
        self.assertIsNotNone(preview.data["previewToken"])
        self.assertFalse(Product.objects.filter(sku="CEM-900").exists())

        applied = self.apply(preview)
        self.assertEqual(applied.status_code, 200)
        product = Product.objects.get(business=self.business, sku="CEM-900")
        inventory = BranchInventory.objects.get(branch=self.branch, product=product)
        self.assertEqual(product.stock, 12)
        self.assertEqual(inventory.stock, 12)
        self.assertTrue(
            StockMovement.objects.filter(
                product=product,
                branch=self.branch,
                movement_type=StockMovement.MovementType.STOCK_IN,
                quantity=12,
            ).exists()
        )
        self.assertTrue(
            BranchStockMovement.objects.filter(
                product=product,
                branch=self.branch,
                movement_type=BranchStockMovement.MovementType.OPENING_STOCK,
                quantity=12,
            ).exists()
        )

    def test_invalid_product_preview_cannot_be_applied(self):
        self.client.force_authenticate(self.owner)
        upload = self.csv_file(
            "tiles.csv",
            "Name,SKU,Category,Product Type,Opening Stock\n"
            "Tile Without Design,TILE-ERR,Tiles,tile,5\n",
        )
        preview = self.preview("products", upload)
        self.assertEqual(preview.status_code, 201)
        self.assertEqual(preview.data["import"]["errorCount"], 1)
        self.assertEqual(preview.data["rows"][0]["action"], "ERROR")
        self.assertIsNone(preview.data["previewToken"])
        self.assertFalse(Product.objects.filter(sku="TILE-ERR").exists())

    def test_xlsx_preview_is_supported(self):
        from openpyxl import Workbook

        self.client.force_authenticate(self.owner)
        workbook = Workbook()
        sheet = workbook.active
        sheet.append(["Name", "SKU", "Category", "Opening Stock"])
        sheet.append(["Excel Cement", "XLSX-1", "Cement", 3])
        buffer = io.BytesIO()
        workbook.save(buffer)
        workbook.close()
        upload = SimpleUploadedFile(
            "products.xlsx",
            buffer.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        preview = self.preview("products", upload)
        self.assertEqual(preview.status_code, 201)
        self.assertEqual(preview.data["import"]["fileType"], "xlsx")
        self.assertEqual(preview.data["rows"][0]["action"], "CREATE")

    def test_customer_and_supplier_imports_reuse_existing_validation(self):
        self.client.force_authenticate(self.owner)
        customer_preview = self.preview(
            "customers",
            self.csv_file(
                "customers.csv",
                "Customer Name,Phone,Email,Address\nAma Doe,0244000000,ama@example.com,Accra\n",
            ),
            branch=False,
        )
        self.assertEqual(customer_preview.status_code, 201)
        self.assertEqual(self.apply(customer_preview).status_code, 200)
        self.assertTrue(
            Customer.objects.filter(
                business=self.business,
                phone="0244000000",
                name="Ama Doe",
            ).exists()
        )

        supplier_preview = self.preview(
            "suppliers",
            self.csv_file(
                "suppliers.csv",
                "Supplier Name,Phone,Email\nSupply Hub,0200000000,supply@example.com\n",
            ),
            branch=False,
        )
        self.assertEqual(supplier_preview.status_code, 201)
        self.assertEqual(self.apply(supplier_preview).status_code, 200)
        self.assertTrue(
            Supplier.objects.filter(
                business=self.business,
                name="Supply Hub",
            ).exists()
        )

    def test_branch_inventory_apply_uses_audited_absolute_stock_change(self):
        self.client.force_authenticate(self.owner)
        product = Product.objects.create(
            business=self.business,
            product_type=Product.ProductType.STANDARD,
            name="Existing Cement",
            sku="CEM-EXIST",
            category="Cement",
            unit=Product.Unit.BAG,
            stock=5,
            low_stock_level=1,
            cost_price=Decimal("20.00"),
            selling_price=Decimal("30.00"),
        )
        BranchInventory.objects.create(
            branch=self.branch,
            product=product,
            stock=5,
            reserved_stock=0,
            low_stock_level=1,
        )
        preview = self.preview(
            "branch_inventory",
            self.csv_file("stock.csv", "SKU,Stock\nCEM-EXIST,9\n"),
        )
        self.assertEqual(preview.status_code, 201)
        self.assertEqual(preview.data["rows"][0]["action"], "UPDATE")
        applied = self.apply(preview)
        self.assertEqual(applied.status_code, 200)
        product.refresh_from_db()
        inventory = BranchInventory.objects.get(branch=self.branch, product=product)
        self.assertEqual(product.stock, 9)
        self.assertEqual(inventory.stock, 9)
        self.assertTrue(
            BranchStockMovement.objects.filter(
                product=product,
                movement_type=BranchStockMovement.MovementType.ADJUSTMENT,
                quantity=4,
            ).exists()
        )

    def test_branch_inventory_rejects_stale_preview_without_partial_change(self):
        self.client.force_authenticate(self.owner)
        product = Product.objects.create(
            business=self.business,
            product_type=Product.ProductType.STANDARD,
            name="Concurrent Cement",
            sku="CEM-CONCURRENT",
            category="Cement",
            unit=Product.Unit.BAG,
            stock=5,
        )
        inventory = BranchInventory.objects.create(
            branch=self.branch,
            product=product,
            stock=5,
            reserved_stock=0,
            low_stock_level=0,
        )
        preview = self.preview(
            "branch_inventory",
            self.csv_file("stock.csv", "SKU,Stock\nCEM-CONCURRENT,10\n"),
        )
        inventory.stock = 6
        inventory.save(update_fields=("stock", "updated_at"))
        product.stock = 6
        product.save(update_fields=("stock", "updated_at"))
        applied = self.apply(preview)
        self.assertEqual(applied.status_code, 400)
        inventory.refresh_from_db()
        product.refresh_from_db()
        self.assertEqual(inventory.stock, 6)
        self.assertEqual(product.stock, 6)
        self.assertEqual(
            DataImport.objects.get(id=preview.data["import"]["id"]).status,
            DataImport.Status.PREVIEWED,
        )

    def test_manager_cannot_preview_bulk_import(self):
        self.client.force_authenticate(self.manager)
        response = self.preview(
            "customers",
            self.csv_file("customers.csv", "Name,Phone\nDenied,0244111111\n"),
            branch=False,
        )
        self.assertEqual(response.status_code, 403)
