from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import JSONParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from businesses.access import get_business_and_role_for_user
from .models import StorefrontOrder
from .serializers import StrictInputSerializer


def authorized_orders(request, business_id):
    business, role = get_business_and_role_for_user(user=request.user, business_id=business_id, membership_roles=('owner', 'manager'))
    return StorefrontOrder.objects.filter(storefront__business=business, branch__business=business)


def order_data(order):
    return {
        'orderId': str(order.id),
        'status': order.status,
        'branchId': str(order.branch_id),
        'customerName': order.customer_name,
        'customerPhone': order.customer_phone,
        'customerNote': order.customer_note,
        'total': str(order.total),
        'currency': order.currency,
        'saleId': str(order.sale_id) if order.sale_id else None,
        'createdAt': order.created_at.isoformat(),
        'completedAt': order.completed_at.isoformat() if order.completed_at else None,
        'items': [{
            'productId': str(item.product_id),
            'name': item.product_name,
            'sku': item.sku,
            'unit': item.unit,
            'quantity': item.quantity,
            'unitPrice': str(item.unit_price),
            'total': str(item.line_total),
        } for item in order.items.all()],
    }


def private_response(data):
    response = Response(data)
    response['Cache-Control'] = 'no-store'
    return response


class OrderPagination(PageNumberPagination):
    page_size = 25


class ShopOrdersAPIView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, business_id):
        rows = authorized_orders(request, business_id)
        state = request.query_params.get('status')
        if state is not None:
            if state not in StorefrontOrder.Status.values:
                raise ValidationError({'status': 'Choose pending, completed or cancelled.'})
            rows = rows.filter(status=state)
        rows = rows.prefetch_related('items').order_by('-created_at', '-id')
        paginator = OrderPagination()
        page = paginator.paginate_queryset(rows, request, view=self)
        response = paginator.get_paginated_response([order_data(order) for order in page])
        response['Cache-Control'] = 'no-store'
        return response


class ShopOrderAPIView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, business_id, order_id):
        order = get_object_or_404(authorized_orders(request, business_id).prefetch_related('items'), pk=order_id)
        return private_response(order_data(order))


class ShopOrderCancelAPIView(APIView):
    permission_classes = (IsAuthenticated,)
    parser_classes = (JSONParser,)

    @transaction.atomic
    def post(self, request, business_id, order_id):
        rows = authorized_orders(request, business_id)
        serializer = StrictInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = get_object_or_404(rows.select_for_update(), pk=order_id)
        if order.status == StorefrontOrder.Status.COMPLETED:
            raise ValidationError({'status': 'A completed order cannot be cancelled here.'})
        replay = order.status == StorefrontOrder.Status.CANCELLED
        if not replay:
            order.status = StorefrontOrder.Status.CANCELLED
            order.save(update_fields=('status', 'updated_at'))
        data = order_data(order)
        data['idempotentReplay'] = replay
        return private_response(data)
