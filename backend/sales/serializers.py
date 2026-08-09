from decimal import Decimal

from django.utils import timezone
from rest_framework import serializers

from .models import Payment, Sale, SaleItem, Waybill
from .services import debt_snapshot


class CheckoutItemSerializer(serializers.Serializer):
    # Accepts one product line from the React point-of-sale cart.

    productId = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1)
    unitPrice = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        min_value=Decimal("0.00"),
    )


class CreateSaleSerializer(serializers.Serializer):
    # Validates the checkout payload before the transactional service runs.

    items = CheckoutItemSerializer(many=True, allow_empty=False)
    customerId = serializers.UUIDField(
        required=False,
        allow_null=True,
    )
    discount = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        min_value=Decimal("0.00"),
        required=False,
        default=Decimal("0.00"),
    )
    amountPaid = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        min_value=Decimal("0.00"),
        required=False,
        default=Decimal("0.00"),
    )
    debtDueDate = serializers.DateField(
        required=False,
        allow_null=True,
    )
    paymentMethod = serializers.ChoiceField(
        choices=Sale.PaymentMethod.choices,
    )
    amountPaidMethod = serializers.ChoiceField(
        choices=Payment.Method.choices,
        required=False,
        allow_blank=True,
        default="",
    )
    mobileMoneyNetwork = serializers.CharField(
        max_length=40,
        required=False,
        allow_blank=True,
        default="",
    )
    mobileMoneyNumber = serializers.RegexField(
        regex=r"^\+?[0-9][0-9\s-]{7,23}$",
        max_length=25,
        required=False,
        allow_blank=True,
        default="",
        error_messages={
            "invalid": "Enter a valid mobile-money phone number.",
        },
    )

    reference = serializers.CharField(
        max_length=180,
        required=False,
        allow_blank=True,
        default="",
    )
    note = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
    )
    receivingAccountId = serializers.UUIDField(
        required=False,
        allow_null=True,
        default=None,
    )

    def validate_items(self, value):
        # Rejects duplicate product lines before stock is locked.
        product_ids = [item["productId"] for item in value]

        if len(product_ids) != len(set(product_ids)):
            raise serializers.ValidationError(
                "Each product can appear only once in a sale."
            )

        return value

    def validate(self, attrs):
        # Validates full payments and any money received on a credit sale.
        payment_method = attrs["paymentMethod"]
        amount_paid = attrs.get("amountPaid", Decimal("0.00"))
        amount_paid_method = attrs.get("amountPaidMethod", "")
        customer_id = attrs.get("customerId")
        network = attrs.get("mobileMoneyNetwork", "").strip()
        phone = attrs.get("mobileMoneyNumber", "").strip()

        if payment_method == Sale.PaymentMethod.CREDIT:
            if not customer_id:
                raise serializers.ValidationError(
                    {
                        "customerId": (
                            "Select a customer for a credit or part-payment sale."
                        )
                    }
                )

            if amount_paid > Decimal("0.00") and not amount_paid_method:
                raise serializers.ValidationError(
                    {
                        "amountPaidMethod": (
                            "Select how the initial payment was received."
                        )
                    }
                )
        else:
            # Full-payment methods are determined by paymentMethod itself.
            attrs["amountPaidMethod"] = ""
            amount_paid_method = ""

        uses_mobile_money = (
            payment_method == Sale.PaymentMethod.MOBILE_MONEY
            or amount_paid_method == Payment.Method.MOBILE_MONEY
        )

        uses_bank_transfer = (
            payment_method == Sale.PaymentMethod.BANK_TRANSFER
            or (
                payment_method == Sale.PaymentMethod.CREDIT
                and amount_paid > Decimal("0.00")
                and amount_paid_method == Payment.Method.BANK_TRANSFER
            )
        )
        reference = attrs.get("reference", "").strip()
        note = attrs.get("note", "").strip()
        receiving_account_id = attrs.get("receivingAccountId")

        if uses_bank_transfer and not reference:
            raise serializers.ValidationError(
                {
                    "reference": (
                        "Enter the bank transfer reference before completing "
                        "the payment."
                    )
                }
            )

        if uses_bank_transfer and not receiving_account_id:
            raise serializers.ValidationError(
                {
                    "receivingAccountId": (
                        "Select the business bank account that received "
                        "this transfer."
                    )
                }
            )

        if not uses_bank_transfer:
            reference = ""
            note = ""
            receiving_account_id = None

        if uses_mobile_money:
            if not network:
                raise serializers.ValidationError(
                    {
                        "mobileMoneyNetwork": (
                            "Select the customer's mobile-money network."
                        )
                    }
                )

            if not phone:
                raise serializers.ValidationError(
                    {
                        "mobileMoneyNumber": (
                            "Enter the customer's mobile-money number."
                        )
                    }
                )
        else:
            network = ""
            phone = ""

        # Keeps the phone number consistent before it reaches a gateway.
        normalized_phone = phone.replace(" ", "").replace("-", "")

        attrs["mobileMoneyNetwork"] = network.lower()
        attrs["mobileMoneyNumber"] = normalized_phone
        attrs["reference"] = reference
        attrs["note"] = note
        attrs["receivingAccountId"] = receiving_account_id

        # Validates the submitted date itself without trusting item prices.
        debt_due_date = attrs.get("debtDueDate")

        if (
            debt_due_date
            and debt_due_date < timezone.localdate()
        ):
            raise serializers.ValidationError(
                {
                    "debtDueDate": (
                        "Debt due date cannot be in the past."
                    )
                }
            )

        return attrs


class DebtPaymentSerializer(serializers.Serializer):
    # Validates a later payment against one unpaid customer invoice.

    amount = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        min_value=Decimal("0.01"),
    )
    saleId = serializers.UUIDField(
        required=False,
        allow_null=True,
    )
    paymentMethod = serializers.ChoiceField(
        choices=Payment.Method.choices,
        default=Payment.Method.CASH,
    )
    reference = serializers.CharField(
        max_length=180,
        required=False,
        allow_blank=True,
        default="",
    )
    note = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
    )
    mobileMoneyNetwork = serializers.CharField(
        max_length=40,
        required=False,
        allow_blank=True,
        default="",
    )
    mobileMoneyNumber = serializers.RegexField(
        regex=r"^\+?[0-9][0-9\s-]{7,23}$",
        max_length=25,
        required=False,
        allow_blank=True,
        default="",
        error_messages={
            "invalid": "Enter a valid mobile-money phone number.",
        },
    )

    def validate(self, attrs):
        # Mobile Money details are required only for a real gateway prompt.
        method = attrs["paymentMethod"]
        network = attrs.get("mobileMoneyNetwork", "").strip()
        phone = attrs.get("mobileMoneyNumber", "").strip()

        if method == Payment.Method.MOBILE_MONEY:
            if not network:
                raise serializers.ValidationError(
                    {
                        "mobileMoneyNetwork": (
                            "Select the customer's mobile-money network."
                        )
                    }
                )

            if not phone:
                raise serializers.ValidationError(
                    {
                        "mobileMoneyNumber": (
                            "Enter the customer's mobile-money number."
                        )
                    }
                )
        else:
            network = ""
            phone = ""

        attrs["reference"] = attrs.get("reference", "").strip()
        attrs["note"] = attrs.get("note", "").strip()
        attrs["mobileMoneyNetwork"] = network.lower()
        attrs["mobileMoneyNumber"] = (
            phone.replace(" ", "").replace("-", "")
        )
        return attrs


class SaleItemSerializer(serializers.ModelSerializer):
    # Returns immutable product and pricing snapshots in React field names.

    productId = serializers.UUIDField(
        source="product_id",
        read_only=True,
    )
    name = serializers.CharField(
        source="product_name",
        read_only=True,
    )
    designCode = serializers.CharField(
        source="design_code",
        read_only=True,
    )
    unitPrice = serializers.DecimalField(
        source="unit_price",
        max_digits=14,
        decimal_places=2,
        read_only=True,
    )
    costPrice = serializers.DecimalField(
        source="cost_price",
        max_digits=14,
        decimal_places=2,
        read_only=True,
    )
    total = serializers.DecimalField(
        source="line_total",
        max_digits=14,
        decimal_places=2,
        read_only=True,
    )

    def get_fields(self):
        # Hides cost information from cashier accounts.
        fields = super().get_fields()

        if self.context.get("current_role") == "cashier":
            fields.pop("costPrice", None)

        return fields

    class Meta:
        model = SaleItem
        fields = (
            "id",
            "productId",
            "name",
            "sku",
            "designCode",
            "quantity",
            "unit",
            "unitPrice",
            "costPrice",
            "total",
        )
        read_only_fields = fields


class PaymentSerializer(serializers.ModelSerializer):
    # Exposes payment status without exposing private gateway credentials.

    businessId = serializers.UUIDField(
        source="business_id",
        read_only=True,
    )
    businessType = serializers.CharField(
        source="business.business_type",
        read_only=True,
    )
    saleNumber = serializers.CharField(
        source="sale.sale_number",
        read_only=True,
        allow_null=True,
    )
    invoiceNumber = serializers.CharField(
        source="sale.invoice_number",
        read_only=True,
        allow_null=True,
    )
    customerName = serializers.SerializerMethodField()
    paymentMethod = serializers.CharField(
        source="method",
        read_only=True,
    )
    type = serializers.CharField(
        source="payment_type",
        read_only=True,
    )
    saleId = serializers.UUIDField(
        source="sale_id",
        read_only=True,
        allow_null=True,
    )
    customerId = serializers.UUIDField(
        source="customer_id",
        read_only=True,
        allow_null=True,
    )
    paymentType = serializers.CharField(
        source="payment_type",
        read_only=True,
    )
    mobileMoneyNetwork = serializers.CharField(
        source="mobile_money_network",
        read_only=True,
    )
    mobileMoneyNumber = serializers.CharField(
        source="mobile_money_number",
        read_only=True,
    )
    gatewayReference = serializers.CharField(
        source="gateway_reference",
        read_only=True,
    )
    providerReference = serializers.CharField(
        source="provider_reference",
        read_only=True,
    )
    receiptNumber = serializers.CharField(
        source="receipt_number",
        read_only=True,
    )
    initiatedBy = serializers.CharField(
        source="initiated_by_name",
        read_only=True,
    )
    receivingAccountId = serializers.UUIDField(
        source="receiving_account_id_snapshot",
        read_only=True,
        allow_null=True,
    )
    receivingAccountType = serializers.CharField(
        source="receiving_account_type",
        read_only=True,
    )
    receivingAccountDisplayName = serializers.CharField(
        source="receiving_account_display_name",
        read_only=True,
    )
    receivingAccountBankName = serializers.CharField(
        source="receiving_account_bank_name",
        read_only=True,
    )
    receivingAccountName = serializers.CharField(
        source="receiving_account_account_name",
        read_only=True,
    )
    receivingAccountNetwork = serializers.CharField(
        source="receiving_account_network",
        read_only=True,
    )
    receivingAccountMaskedNumber = serializers.CharField(
        source="receiving_account_masked_number",
        read_only=True,
    )
    failureReason = serializers.CharField(
        source="failure_reason",
        read_only=True,
    )
    verifiedAt = serializers.DateTimeField(
        source="verified_at",
        read_only=True,
    )
    createdAt = serializers.DateTimeField(
        source="created_at",
        read_only=True,
    )
    updatedAt = serializers.DateTimeField(
        source="updated_at",
        read_only=True,
    )
    overdueChargePaid = serializers.SerializerMethodField()
    principalPaid = serializers.SerializerMethodField()
    saleOutstandingBalance = serializers.DecimalField(
        source="sale.outstanding_balance",
        max_digits=14,
        decimal_places=2,
        read_only=True,
        allow_null=True,
    )
    customerOutstandingBalance = serializers.DecimalField(
        source="customer.outstanding_balance",
        max_digits=14,
        decimal_places=2,
        read_only=True,
        allow_null=True,
    )
    remainingOverdueCharge = serializers.SerializerMethodField()
    totalDebtPayable = serializers.SerializerMethodField()

    def _debt_allocation(self, obj):
        # Reads the audited charge/principal split when it exists.
        return (
            obj.debt_allocation
            if hasattr(obj, "debt_allocation")
            else None
        )

    def _sale_debt_snapshot(self, obj):
        # Caches one current debt calculation per serialized payment.
        if not obj.sale_id:
            return {
                "overdue_charge": Decimal("0.00"),
                "total_debt_payable": Decimal("0.00"),
            }

        cache = getattr(self, "_debt_snapshot_cache", {})
        cache_key = str(obj.sale_id)

        if cache_key not in cache:
            cache[cache_key] = debt_snapshot(sale=obj.sale)
            self._debt_snapshot_cache = cache

        return cache[cache_key]

    def get_overdueChargePaid(self, obj):
        # Reports the amount applied to overdue charges.
        allocation = self._debt_allocation(obj)
        return (
            allocation.overdue_charge_paid
            if allocation
            else Decimal("0.00")
        )

    def get_principalPaid(self, obj):
        # Reports the amount that reduced invoice principal.
        allocation = self._debt_allocation(obj)
        return (
            allocation.principal_paid
            if allocation
            else Decimal("0.00")
        )

    def get_remainingOverdueCharge(self, obj):
        # Returns the unpaid charge after this payment.
        return self._sale_debt_snapshot(obj)["overdue_charge"]

    def get_totalDebtPayable(self, obj):
        # Returns the invoice total still payable after this payment.
        return self._sale_debt_snapshot(obj)["total_debt_payable"]

    def get_customerName(self, obj):
        # Returns the linked customer name or the sale snapshot.
        if obj.customer_id:
            return obj.customer.name

        if obj.sale_id:
            return obj.sale.customer_name

        return "Walk-in customer"

    class Meta:
        model = Payment
        fields = (
            "id",
            "businessId",
            "businessType",
            "saleId",
            "saleNumber",
            "invoiceNumber",
            "customerId",
            "customerName",
            "paymentType",
            "type",
            "method",
            "paymentMethod",
            "status",
            "amount",
            "mobileMoneyNetwork",
            "mobileMoneyNumber",
            "gateway",
            "gatewayReference",
            "providerReference",
            "receiptNumber",
            "reference",
            "note",
            "receivingAccountId",
            "receivingAccountType",
            "receivingAccountDisplayName",
            "receivingAccountBankName",
            "receivingAccountName",
            "receivingAccountNetwork",
            "receivingAccountMaskedNumber",
            "failureReason",
            "initiatedBy",
            "verifiedAt",
            "createdAt",
            "updatedAt",
            "overdueChargePaid",
            "principalPaid",
            "saleOutstandingBalance",
            "customerOutstandingBalance",
            "remainingOverdueCharge",
            "totalDebtPayable",
        )
        read_only_fields = fields



class WaybillSerializer(serializers.ModelSerializer):
    # Returns the camelCase delivery document expected by React.

    waybillNumber = serializers.CharField(
        source="waybill_number",
        read_only=True,
    )
    recipientName = serializers.CharField(
        source="recipient_name",
        read_only=True,
    )
    recipientPhone = serializers.CharField(
        source="recipient_phone",
        read_only=True,
    )
    deliveryAddress = serializers.CharField(
        source="delivery_address",
        read_only=True,
    )
    dispatchDate = serializers.DateField(
        source="dispatch_date",
        read_only=True,
    )
    driverName = serializers.CharField(
        source="driver_name",
        read_only=True,
    )
    vehicleNumber = serializers.CharField(
        source="vehicle_number",
        read_only=True,
    )
    deliveryNotes = serializers.CharField(
        source="delivery_notes",
        read_only=True,
    )
    createdAt = serializers.DateTimeField(
        source="created_at",
        read_only=True,
    )
    updatedAt = serializers.DateTimeField(
        source="updated_at",
        read_only=True,
    )

    class Meta:
        model = Waybill
        fields = (
            "waybillNumber",
            "recipientName",
            "recipientPhone",
            "deliveryAddress",
            "dispatchDate",
            "driverName",
            "vehicleNumber",
            "deliveryNotes",
            "status",
            "createdAt",
            "updatedAt",
        )
        read_only_fields = fields


class WaybillUpsertSerializer(serializers.Serializer):
    # Validates new waybills and later detail/status updates.

    recipientName = serializers.CharField(
        source="recipient_name",
        max_length=180,
        trim_whitespace=True,
    )
    recipientPhone = serializers.CharField(
        source="recipient_phone",
        max_length=30,
        trim_whitespace=True,
        required=False,
        allow_blank=True,
        default="",
    )
    deliveryAddress = serializers.CharField(
        source="delivery_address",
        trim_whitespace=True,
        allow_blank=False,
    )
    dispatchDate = serializers.DateField(
        source="dispatch_date",
    )
    driverName = serializers.CharField(
        source="driver_name",
        max_length=180,
        trim_whitespace=True,
        required=False,
        allow_blank=True,
        default="",
    )
    vehicleNumber = serializers.CharField(
        source="vehicle_number",
        max_length=80,
        trim_whitespace=True,
        required=False,
        allow_blank=True,
        default="",
    )
    deliveryNotes = serializers.CharField(
        source="delivery_notes",
        trim_whitespace=True,
        required=False,
        allow_blank=True,
        default="",
    )
    status = serializers.ChoiceField(
        choices=Waybill.Status.choices,
        required=False,
        default=Waybill.Status.PENDING,
    )


class SaleSerializer(serializers.ModelSerializer):
    # Returns the complete invoice-ready sale in React field names.

    businessId = serializers.UUIDField(
        source="business_id",
        read_only=True,
    )
    businessType = serializers.CharField(
        source="business.business_type",
        read_only=True,
    )
    customerId = serializers.UUIDField(
        source="customer_id",
        read_only=True,
        allow_null=True,
    )
    customerName = serializers.CharField(
        source="customer_name",
        read_only=True,
    )
    customerPhone = serializers.CharField(
        source="customer_phone",
        read_only=True,
    )
    saleNumber = serializers.CharField(
        source="sale_number",
        read_only=True,
    )
    invoiceNumber = serializers.CharField(
        source="invoice_number",
        read_only=True,
    )
    receiptNumber = serializers.SerializerMethodField()
    latestReceiptNumber = serializers.SerializerMethodField()
    paymentMethod = serializers.CharField(
        source="payment_method",
        read_only=True,
    )
    amountPaid = serializers.DecimalField(
        source="amount_paid",
        max_digits=14,
        decimal_places=2,
        read_only=True,
    )
    outstandingBalance = serializers.DecimalField(
        source="outstanding_balance",
        max_digits=14,
        decimal_places=2,
        read_only=True,
    )
    overdueCharge = serializers.SerializerMethodField()
    totalDebtPayable = serializers.SerializerMethodField()
    daysOverdue = serializers.SerializerMethodField()
    overduePercentage = serializers.SerializerMethodField()
    debtDueDate = serializers.DateField(
        source="debt_due_date",
        read_only=True,
        allow_null=True,
    )
    debtPrincipalAtDue = serializers.DecimalField(
        source="debt_principal_at_due",
        max_digits=14,
        decimal_places=2,
        read_only=True,
    )
    cashier = serializers.CharField(
        source="cashier_name",
        read_only=True,
    )
    reservationExpiresAt = serializers.DateTimeField(
        source="reservation_expires_at",
        read_only=True,
    )
    completedAt = serializers.DateTimeField(
        source="completed_at",
        read_only=True,
    )
    createdAt = serializers.DateTimeField(
        source="created_at",
        read_only=True,
    )
    updatedAt = serializers.DateTimeField(
        source="updated_at",
        read_only=True,
    )
    items = SaleItemSerializer(many=True, read_only=True)
    payments = PaymentSerializer(many=True, read_only=True)
    waybill = serializers.SerializerMethodField()

    def _current_debt_snapshot(self, obj):
        # Caches one current debt calculation per serialized sale.
        cache = getattr(self, "_debt_snapshot_cache", {})
        cache_key = str(obj.pk)

        if cache_key not in cache:
            cache[cache_key] = debt_snapshot(sale=obj)
            self._debt_snapshot_cache = cache

        return cache[cache_key]

    def get_overdueCharge(self, obj):
        # Returns only the currently unpaid overdue charge.
        return self._current_debt_snapshot(obj)["overdue_charge"]

    def get_totalDebtPayable(self, obj):
        # Returns principal plus the currently unpaid overdue charge.
        return self._current_debt_snapshot(obj)["total_debt_payable"]

    def get_daysOverdue(self, obj):
        # Returns zero until the original debt due date has passed.
        return self._current_debt_snapshot(obj)["days_overdue"]

    def get_overduePercentage(self, obj):
        # Returns the active non-compounding overdue tier.
        return self._current_debt_snapshot(obj)["overdue_percentage"]

    class Meta:
        model = Sale
        fields = (
            "id",
            "businessId",
            "businessType",
            "customerId",
            "customerName",
            "customerPhone",
            "saleNumber",
            "invoiceNumber",
            "receiptNumber",
            "latestReceiptNumber",
            "waybill",
            "items",
            "subtotal",
            "discount",
            "total",
            "amountPaid",
            "outstandingBalance",
            "overdueCharge",
            "totalDebtPayable",
            "daysOverdue",
            "overduePercentage",
            "debtDueDate",
            "debtPrincipalAtDue",
            "paymentMethod",
            "status",
            "cashier",
            "reservationExpiresAt",
            "completedAt",
            "createdAt",
            "updatedAt",
            "payments",
        )
        read_only_fields = fields

    def _latest_successful_payment(self, obj):
        return next(
            (
                payment
                for payment in obj.payments.all()
                if payment.status == Payment.Status.SUCCESSFUL
            ),
            None,
        )

    def get_receiptNumber(self, obj):
        # Returns the first receipt issued for the sale.
        payment = next(
            (
                item
                for item in reversed(list(obj.payments.all()))
                if item.status == Payment.Status.SUCCESSFUL
            ),
            None,
        )
        return payment.receipt_number if payment else None

    def get_latestReceiptNumber(self, obj):
        # Returns the newest successfully issued receipt.
        payment = self._latest_successful_payment(obj)
        return payment.receipt_number if payment else None

    def get_waybill(self, obj):
        # Returns the persisted delivery document without changing sale shape.
        waybill = getattr(obj, "waybill", None)

        if not waybill:
            return None

        return WaybillSerializer(waybill).data
