from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import JSONParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from inventory.photo_urls import product_photo_url
from inventory.models import BranchInventory
from .models import Storefront, StorefrontListing
from .services import create_pending_order, require_public_storefront


class PublicShopReadThrottle(AnonRateThrottle):
    scope = 'storefront_read'
    rate = '60/min'


class PublicShopOrderThrottle(AnonRateThrottle):
    scope = 'storefront_order'
    rate = '10/hour'


class PublicShopPagination(PageNumberPagination):
    page_size = 24


class PublicShopAPIView(APIView):
    authentication_classes = ()
    permission_classes = (AllowAny,)
    throttle_classes = (PublicShopReadThrottle,)

    def get(self, request, shop_slug):
        shop = get_object_or_404(
            Storefront.objects.select_related('business', 'branch'),
            business__slug=shop_slug,
        )
        require_public_storefront(shop)
        query = request.query_params.get('q', '').strip()
        if len(query) > 100:
            raise ValidationError({'q': 'Search must be 100 characters or fewer.'})
        listings = StorefrontListing.objects.filter(
            storefront=shop, is_published=True,
            product__business=shop.business, product__is_active=True,
        ).select_related('product', 'product__uploaded_photo').order_by('product__name', 'id')
        if query:
            listings = listings.filter(
                Q(product__name__icontains=query)
                | Q(product__category__icontains=query)
                | Q(product__design_code__icontains=query)
                | Q(product__style_code__icontains=query)
            )
        paginator = PublicShopPagination()
        page = paginator.paginate_queryset(listings, request, view=self)
        inventory = {row.product_id: row for row in BranchInventory.objects.filter(
            branch=shop.branch, product_id__in=[listing.product_id for listing in page],
        )}
        products = []
        for listing in page:
            product = listing.product
            row = inventory.get(product.id)
            available = row.available_stock if row is not None else 0
            products.append({
                'listingId': str(listing.id),
                'productId': str(product.id),
                'name': product.name,
                'category': product.category,
                'brand': product.brand,
                'unit': product.unit,
                'price': str(product.selling_price),
                'currency': 'GHS',
                'size': product.size,
                'color': product.color,
                'designCode': product.design_code,
                'styleCode': product.style_code,
                'description': listing.description,
                'imageUrl': product_photo_url(product, request) or listing.image_url,
                'availableQuantity': available,
                'inStock': available > 0,
            })
        response = paginator.get_paginated_response(products)
        response.data['shop'] = {
            'name': shop.business.name,
            'slug': shop.business.slug,
            'introduction': shop.introduction,
            'contactPhone': shop.contact_phone,
            'whatsappEnabled': bool(shop.whatsapp_enabled and shop.whatsapp_phone),
            'whatsappPhone': shop.whatsapp_phone if shop.whatsapp_enabled and shop.whatsapp_phone else '',
            'currency': 'GHS',
        }
        response['Cache-Control'] = 'no-store'
        return response


class PublicShopOrderAPIView(APIView):
    authentication_classes = ()
    permission_classes = (AllowAny,)
    throttle_classes = (PublicShopOrderThrottle,)
    parser_classes = (JSONParser,)

    def post(self, request, shop_slug):
        order, replay = create_pending_order(shop_slug=shop_slug, data=request.data)
        response = Response({
            'orderId': str(order.id),
            'status': order.status,
            'total': str(order.total),
            'currency': order.currency,
            'idempotentReplay': replay,
        }, status=200 if replay else 201)
        response['Cache-Control'] = 'no-store'
        return response
