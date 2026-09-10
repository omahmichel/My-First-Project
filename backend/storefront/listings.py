from django.core.exceptions import ValidationError as ModelValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import JSONParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from inventory.models import Product
from .management import owner_business
from .models import Storefront, StorefrontListing
from .serializers import StrictInputSerializer


class ListingInput(StrictInputSerializer):
    isPublished = serializers.BooleanField(required=False)
    description = serializers.CharField(max_length=2000, required=False, allow_blank=True)
    imageUrl = serializers.URLField(max_length=1000, required=False, allow_blank=True)


def listing_data(listing):
    return {
        'listingId': str(listing.id),
        'productId': str(listing.product_id),
        'name': listing.product.name,
        'sku': listing.product.sku,
        'price': str(listing.product.selling_price),
        'currency': 'GHS',
        'productActive': listing.product.is_active,
        'isPublished': listing.is_published,
        'description': listing.description,
        'imageUrl': listing.image_url,
    }


class ListingPagination(PageNumberPagination):
    page_size = 30


class ShopListingsAPIView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, business_id):
        business = owner_business(request, business_id)
        shop = get_object_or_404(Storefront, business=business)
        rows = StorefrontListing.objects.filter(storefront=shop, product__business=business).select_related('product').order_by('product__name', 'id')
        paginator = ListingPagination()
        page = paginator.paginate_queryset(rows, request, view=self)
        response = paginator.get_paginated_response([listing_data(row) for row in page])
        response['Cache-Control'] = 'no-store'
        return response


class ShopListingAPIView(APIView):
    permission_classes = (IsAuthenticated,)
    parser_classes = (JSONParser,)

    @transaction.atomic
    def put(self, request, business_id, product_id):
        business = owner_business(request, business_id)
        serializer = ListingInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        shop = get_object_or_404(Storefront.objects.select_for_update(), business=business)
        product = get_object_or_404(Product.objects.select_for_update(), pk=product_id, business=business)
        listing = StorefrontListing.objects.filter(storefront=shop, product=product).first()
        created = listing is None
        if created:
            listing = StorefrontListing(storefront=shop, product=product)
        for key, field in (('isPublished', 'is_published'), ('description', 'description'), ('imageUrl', 'image_url')):
            if key in serializer.validated_data:
                setattr(listing, field, serializer.validated_data[key])
        try:
            listing.save()
            from .social import sync_social_listing
            sync_social_listing(listing)
        except ModelValidationError as exc:
            raise ValidationError(exc.message_dict if hasattr(exc, 'message_dict') else exc.messages) from exc
        response = Response(listing_data(listing), status=201 if created else 200)
        response['Cache-Control'] = 'no-store'
        return response
