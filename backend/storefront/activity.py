from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import JSONParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView
from .models import Storefront, StorefrontListing, StorefrontActivity
from .serializers import StrictInputSerializer
from .services import require_public_storefront


class ActivityInputSerializer(StrictInputSerializer):
    eventId = serializers.UUIDField()
    sessionId = serializers.UUIDField()
    eventType = serializers.ChoiceField(choices=StorefrontActivity.EventType.choices)
    listingId = serializers.UUIDField(required=False, allow_null=True, default=None)

    def validate(self, attrs):
        shop_event = attrs['eventType'] in ('shop_visit', 'product_search')
        if shop_event and attrs['listingId'] is not None:
            raise ValidationError({'listingId': 'This event must not reference a product.'})
        if not shop_event and attrs['listingId'] is None:
            raise ValidationError({'listingId': 'A product listing is required.'})
        return attrs


class ActivityThrottle(AnonRateThrottle):
    scope = 'storefront_activity'
    rate = '120/min'


@transaction.atomic
def record_activity(*, shop_slug, data):
    serializer = ActivityInputSerializer(data=data)
    serializer.is_valid(raise_exception=True)
    values = serializer.validated_data
    shop = get_object_or_404(Storefront.objects.select_for_update().select_related('business', 'branch'), business__slug=shop_slug)
    require_public_storefront(shop)
    listing = None
    if values['listingId'] is not None:
        listing = get_object_or_404(StorefrontListing, id=values['listingId'], storefront=shop, is_published=True, product__is_active=True, product__business=shop.business)
    existing = StorefrontActivity.objects.filter(storefront=shop, event_id=values['eventId']).first()
    if existing:
        actual = (existing.session_id, existing.event_type, existing.listing_id)
        expected = (values['sessionId'], values['eventType'], values['listingId'])
        if actual != expected:
            raise ValidationError({'eventId': 'This event ID was used for different activity.'})
        return True
    StorefrontActivity.objects.create(storefront=shop, event_id=values['eventId'], session_id=values['sessionId'], event_type=values['eventType'], listing=listing)
    return False


class PublicActivityAPIView(APIView):
    authentication_classes = ()
    permission_classes = (AllowAny,)
    throttle_classes = (ActivityThrottle,)
    parser_classes = (JSONParser,)

    def post(self, request, shop_slug):
        replay = record_activity(shop_slug=shop_slug, data=request.data)
        response = Response({'accepted': True, 'idempotentReplay': replay}, status=200 if replay else 201)
        response['Cache-Control'] = 'no-store'
        return response
