"""Social publishing preparation; this module makes no external requests."""
from inventory.photo_urls import product_photo_url
from inventory.video_urls import product_video_url
import hashlib
import json
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import JSONParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from .management import owner_business
from .public_urls import public_shop_path, public_shop_url
from .models import Storefront, StorefrontListing, SocialChannel, SocialPublishingJob, SocialDeliveryAttempt
from .serializers import StrictInputSerializer


def private_response(data):
    response = Response(data)
    response['Cache-Control'] = 'no-store'
    return response


def cancel_jobs(rows):
    rows.exclude(status=SocialPublishingJob.Status.CANCELLED).update(
        status=SocialPublishingJob.Status.CANCELLED, updated_at=timezone.now())


@transaction.atomic
def sync_social_listing(listing):
    # All preference, shop and listing mutations serialize on the same shop row.
    shop = Storefront.objects.select_for_update().select_related('business', 'branch').get(pk=listing.storefront_id)
    listing = StorefrontListing.objects.select_related('product').get(pk=listing.pk)
    rows = SocialPublishingJob.objects.filter(listing=listing)
    eligible = (shop.is_published and shop.branch.is_active and listing.is_published
                and listing.product.is_active and listing.product.business_id == shop.business_id)
    if not eligible:
        cancel_jobs(rows)
        return
    payload = {
        'listingId': str(listing.pk), 'productId': str(listing.product_id),
        'name': listing.product.name, 'sku': listing.product.sku,
        'price': str(listing.product.selling_price), 'currency': 'GHS',
        'description': listing.description, 'imageUrl': product_photo_url(listing.product) or listing.image_url,
        'videoUrl': product_video_url(listing.product),
        'shopPath': public_shop_path(shop),
    }
    fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    cancel_jobs(rows.filter(channel__auto_publish=False))
    for channel in shop.social_channels.filter(auto_publish=True):
        job, created = SocialPublishingJob.objects.get_or_create(
            channel=channel, listing=listing,
            defaults={'payload': payload, 'fingerprint': fingerprint})
        if not created and (job.fingerprint != fingerprint or job.status != SocialPublishingJob.Status.PENDING_CONNECTION):
            job.payload = payload
            job.fingerprint = fingerprint
            job.status = SocialPublishingJob.Status.PENDING_CONNECTION
            job.save(update_fields=('payload', 'fingerprint', 'status', 'updated_at'))


@transaction.atomic
def sync_social_shop(shop):
    shop = Storefront.objects.select_for_update().get(pk=shop.pk)
    for listing in shop.listings.all().iterator():
        sync_social_listing(listing)


def channel_data(shop):
    # Connection credentials are business-scoped and encrypted in integrations.
    # Only safe connection metadata is exposed to the frontend.
    from .facebook_social import facebook_connection_summary, instagram_connection_summary

    existing = {row.platform: row for row in shop.social_channels.all()}
    facebook = facebook_connection_summary(shop.business)
    instagram = instagram_connection_summary(shop.business)
    channels = []
    for value, label in SocialChannel.Platform.choices:
        row = {
            'platform': value,
            'label': label,
            'autoPublish': existing[value].auto_publish if value in existing else False,
            'connectionStatus': 'not_connected',
            'deliveryAvailable': False,
        }
        if value == SocialChannel.Platform.FACEBOOK:
            row.update(facebook)
        elif value == SocialChannel.Platform.INSTAGRAM:
            row.update(instagram)
        channels.append(row)
    return {
        'channels': channels,
        'shopPath': public_shop_path(shop),
        'shopUrl': public_shop_url(shop),
    }


class SocialChannelInput(StrictInputSerializer):
    autoPublish = serializers.BooleanField(required=True)


class SocialChannelsAPIView(APIView):
    permission_classes = (IsAuthenticated,)
    parser_classes = (JSONParser,)

    def get(self, request, business_id):
        business = owner_business(request, business_id)
        shop = get_object_or_404(Storefront, business=business)
        return private_response(channel_data(shop))


class SocialChannelAPIView(APIView):
    permission_classes = (IsAuthenticated,)
    parser_classes = (JSONParser,)

    @transaction.atomic
    def patch(self, request, business_id, platform):
        business = owner_business(request, business_id)
        if platform not in SocialChannel.Platform.values:
            from rest_framework.exceptions import NotFound
            raise NotFound('Unknown social channel.')
        data = SocialChannelInput(data=request.data)
        data.is_valid(raise_exception=True)
        shop = get_object_or_404(Storefront.objects.select_for_update(), business=business)
        SocialChannel.objects.update_or_create(
            storefront=shop, platform=platform,
            defaults={'auto_publish': data.validated_data['autoPublish']})
        sync_social_shop(shop)
        return private_response(channel_data(shop))


class SocialJobsPagination(PageNumberPagination):
    page_size = 20


def _delivery_data(row):
    attempt = (
        row.delivery_attempts.filter(fingerprint=row.fingerprint)
        .order_by('-updated_at', '-id')
        .first()
    )
    if attempt is None:
        return {
            'deliveryStatus': 'not_sent',
            'deliveryAttemptCount': 0,
            'deliveryError': '',
            'remotePostId': '',
            'remoteContainerId': '',
            'publishedAt': None,
        }
    return {
        'deliveryStatus': attempt.status,
        'deliveryAttemptCount': attempt.attempt_count,
        'deliveryError': attempt.error_message,
        'remotePostId': (
            attempt.provider_post_id
            if attempt.status == SocialDeliveryAttempt.Status.SUCCEEDED
            else ''
        ),
        'remoteContainerId': attempt.provider_container_id,
        'publishedAt': (
            attempt.completed_at.isoformat()
            if attempt.status == SocialDeliveryAttempt.Status.SUCCEEDED
            and attempt.completed_at
            else None
        ),
    }


class SocialJobsAPIView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, business_id):
        business = owner_business(request, business_id)
        shop = get_object_or_404(Storefront, business=business)
        rows = SocialPublishingJob.objects.filter(channel__storefront=shop, listing__storefront=shop).select_related('channel', 'listing__product')
        paginator = SocialJobsPagination()
        page = paginator.paginate_queryset(rows, request, view=self)
        response = paginator.get_paginated_response([
            {'id': str(row.pk), 'platform': row.channel.platform,
             'productName': row.listing.product.name, 'status': row.status,
             'updatedAt': row.updated_at.isoformat(), **_delivery_data(row)}
            for row in page])
        response['Cache-Control'] = 'no-store'
        return response
