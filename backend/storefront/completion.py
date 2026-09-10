from .customer_matching import resolve_order_customer
from decimal import Decimal
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import JSONParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from businesses.models import Branch
from sales.models import Sale
from sales.serializers import CreateSaleSerializer
from sales.services import create_completed_sale
from .models import StorefrontOrder
from .orders import authorized_orders, order_data, private_response
from .serializers import StrictInputSerializer


class CompleteOrderInput(StrictInputSerializer):
    cashReceived = serializers.BooleanField()
    amountReceived = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal('0.01'))

    def validate_cashReceived(self, value):
        if not value:
            raise serializers.ValidationError('Confirm that the cash has actually been received.')
        return value


class ShopOrderCompleteAPIView(APIView):
    permission_classes = (IsAuthenticated,)
    parser_classes = (JSONParser,)

    @transaction.atomic
    def post(self, request, business_id, order_id):
        rows = authorized_orders(request, business_id)
        serializer = CompleteOrderInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        order = get_object_or_404(rows.select_for_update(), pk=order_id)
        if data['amountReceived'] != order.total:
            raise ValidationError({'amountReceived': 'Enter the exact order total received in cash.'})
        if order.status == StorefrontOrder.Status.CANCELLED:
            raise ValidationError({'status': 'A cancelled order cannot be completed.'})
        replay = order.status == StorefrontOrder.Status.COMPLETED
        if replay:
            sale = order.sale
        else:
            branch = get_object_or_404(Branch, pk=order.branch_id, business_id=business_id, is_active=True)
            items = list(order.items.all())
            total = sum((item.quantity * item.unit_price for item in items), Decimal('0.00'))
            if not items or total != order.total or any(item.line_total != item.quantity * item.unit_price for item in items):
                raise ValidationError({'items': 'The order totals require review before completion.'})
            key = 'storefront-order-' + str(order.id)
            if Sale.objects.filter(business_id=business_id, idempotency_key=key).exists():
                raise ValidationError({'detail': 'An existing sale requires reconciliation before this order can be completed.'})
            customer = resolve_order_customer(order=order, user=request.user)
            checkout = CreateSaleSerializer(data={
                'customerId': str(customer.id),
                'paymentMethod': 'cash',
                'items': [{'productId': str(item.product_id), 'quantity': item.quantity, 'unitPrice': str(item.unit_price)} for item in items],
            })
            checkout.is_valid(raise_exception=True)
            sale, unused = create_completed_sale(business=order.storefront.business, user=request.user, data=checkout.validated_data, idempotency_key=key, branch=branch)
            if sale.total != order.total or sale.status != Sale.Status.COMPLETED:
                raise ValidationError({'detail': 'Sale completion did not match the order.'})
            order.sale = sale
            order.status = StorefrontOrder.Status.COMPLETED
            order.completed_by = request.user
            order.completed_at = timezone.now()
            order.save(update_fields=('sale', 'status', 'completed_by', 'completed_at', 'updated_at'))
            sale.save(update_fields=('customer_name', 'customer_phone', 'updated_at'))
        result = order_data(order)
        result.update({'idempotentReplay': replay, 'saleNumber': sale.sale_number, 'invoiceNumber': sale.invoice_number, 'receiptNumber': sale.payments.filter(status='successful').values_list('receipt_number', flat=True).first()})
        return private_response(result)
