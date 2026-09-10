from django.core.exceptions import ValidationError as ModelValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import JSONParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from businesses.access import get_business_and_role_for_user
from businesses.models import Business, Branch
from .models import Storefront
from .serializers import StrictInputSerializer


class ShopSettingsInput(StrictInputSerializer):
    branchId = serializers.UUIDField(required=False)
    isPublished = serializers.BooleanField(required=False)
    introduction = serializers.CharField(max_length=500, required=False, allow_blank=True)
    contactPhone = serializers.RegexField(regex=r'^\+?[0-9][0-9 -]{7,23}$', max_length=30, required=False, allow_blank=True)

    def validate_contactPhone(self, value):
        return value.replace(' ', '').replace('-', '')


def owner_business(request, business_id):
    business, role = get_business_and_role_for_user(user=request.user, business_id=business_id)
    if role != 'owner':
        raise PermissionDenied('Only the business owner can change shop publishing settings.')
    return business


def settings_response(business, shop):
    response = Response({
        'configured': shop is not None,
        'shopId': str(shop.id) if shop else None,
        'name': business.name,
        'slug': business.slug,
        'shopPath': '/shops/' + business.slug,
        'branchId': str(shop.branch_id) if shop else None,
        'isPublished': shop.is_published if shop else False,
        'introduction': shop.introduction if shop else '',
        'contactPhone': shop.contact_phone if shop else '',
    })
    response['Cache-Control'] = 'no-store'
    return response


class ShopSettingsAPIView(APIView):
    permission_classes = (IsAuthenticated,)
    parser_classes = (JSONParser,)

    def get(self, request, business_id):
        business = owner_business(request, business_id)
        shop = Storefront.objects.filter(business=business).first()
        return settings_response(business, shop)

    @transaction.atomic
    def patch(self, request, business_id):
        business = owner_business(request, business_id)
        Business.objects.select_for_update().get(pk=business.pk)
        serializer = ShopSettingsInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        shop = Storefront.objects.select_for_update().filter(business=business).first()
        if shop is None:
            if 'branchId' not in data:
                raise ValidationError({'branchId': 'Choose a fulfilment branch to create your shop.'})
            shop = Storefront(business=business)
        if 'branchId' in data:
            shop.branch = get_object_or_404(Branch, pk=data['branchId'], business=business, is_active=True)
        for key, field in (('isPublished', 'is_published'), ('introduction', 'introduction'), ('contactPhone', 'contact_phone')):
            if key in data:
                setattr(shop, field, data[key])
        try:
            shop.save()
        except ModelValidationError as exc:
            raise ValidationError(exc.message_dict if hasattr(exc, 'message_dict') else exc.messages) from exc
        return settings_response(business, shop)
