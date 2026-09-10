import uuid

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db import models


class Storefront(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.OneToOneField(
        'businesses.Business', on_delete=models.CASCADE,
        related_name='storefront',
    )
    branch = models.ForeignKey(
        'businesses.Branch', on_delete=models.PROTECT,
        related_name='storefronts',
    )
    is_published = models.BooleanField(default=False)
    introduction = models.CharField(max_length=500, blank=True)
    contact_phone = models.CharField(max_length=30, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        errors = {}
        if self.branch_id and self.business_id:
            if self.branch.business_id != self.business_id:
                errors['branch'] = 'The fulfilment branch must belong to this business.'
            elif self.is_published and not self.branch.is_active:
                errors['branch'] = 'Choose an active fulfilment branch before publishing.'
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.business.name

class StorefrontListing(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    storefront = models.ForeignKey(
        Storefront, on_delete=models.CASCADE, related_name='listings',
    )
    product = models.ForeignKey(
        'inventory.Product', on_delete=models.PROTECT,
        related_name='storefront_listings',
    )
    is_published = models.BooleanField(default=False)
    description = models.TextField(max_length=2000, blank=True)
    image_url = models.URLField(
        max_length=1000, blank=True,
        validators=[URLValidator(schemes=['https'])],
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('product__name',)
        constraints = [
            models.UniqueConstraint(
                fields=('storefront', 'product'),
                name='uniq_storefront_listing_product',
            ),
        ]
        indexes = [models.Index(fields=('storefront', 'is_published'))]

    def clean(self):
        if self.storefront_id and self.product_id:
            if self.product.business_id != self.storefront.business_id:
                raise ValidationError({
                    'product': 'The product must belong to the storefront business.',
                })
            if self.is_published and not self.product.is_active:
                raise ValidationError({
                    'product': 'An inactive product cannot be published.',
                })

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.product.name

class StorefrontOrder(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending review'
        COMPLETED = 'completed', 'Completed'
        CANCELLED = 'cancelled', 'Cancelled'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    storefront = models.ForeignKey(
        Storefront, on_delete=models.PROTECT, related_name='orders',
    )
    branch = models.ForeignKey(
        'businesses.Branch', on_delete=models.PROTECT,
        related_name='storefront_orders',
    )
    idempotency_key = models.UUIDField()
    request_fingerprint = models.CharField(max_length=64)
    customer_name = models.CharField(max_length=180)
    customer_phone = models.CharField(max_length=30)
    customer_note = models.CharField(max_length=1000, blank=True)
    currency = models.CharField(max_length=3, default='GHS', choices=[('GHS', 'Ghana cedi')])
    total = models.DecimalField(max_digits=14, decimal_places=2)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    sale = models.OneToOneField(
        'sales.Sale', on_delete=models.PROTECT,
        related_name='storefront_order', blank=True, null=True,
    )
    completed_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL,
        related_name='completed_storefront_orders', blank=True, null=True,
    )
    completed_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created_at',)
        constraints = [
            models.UniqueConstraint(
                fields=('storefront', 'idempotency_key'),
                name='uniq_storefront_order_request',
            ),
            models.CheckConstraint(
                condition=models.Q(total__gte=0),
                name='storefront_order_total_nonneg',
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(status='completed', sale__isnull=False, completed_at__isnull=False)
                    | models.Q(status__in=['pending', 'cancelled'], sale__isnull=True, completed_at__isnull=True)
                ),
                name='storefront_order_sale_state',
            ),
        ]
        indexes = [models.Index(fields=('storefront', 'status', 'created_at'))]

    def clean(self):
        errors = {}
        if self.storefront_id and self.branch_id:
            if self.branch.business_id != self.storefront.business_id:
                errors['branch'] = 'The order branch must belong to the storefront business.'
        if self.sale_id and self.storefront_id:
            if self.sale.business_id != self.storefront.business_id:
                errors['sale'] = 'The sale must belong to the storefront business.'
            elif self.sale.branch_id != self.branch_id:
                errors['sale'] = 'The sale must use the order fulfilment branch.'
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return str(self.id)

class StorefrontOrderItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(
        StorefrontOrder, on_delete=models.CASCADE, related_name='items',
    )
    product = models.ForeignKey(
        'inventory.Product', on_delete=models.PROTECT,
        related_name='storefront_order_items',
    )
    product_name = models.CharField(max_length=180)
    sku = models.CharField(max_length=100)
    unit = models.CharField(max_length=20)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=14, decimal_places=2)
    line_total = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        ordering = ('product_name', 'id')
        constraints = [
            models.UniqueConstraint(
                fields=('order', 'product'), name='uniq_storefront_order_product',
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0), name='storefront_item_quantity_pos',
            ),
            models.CheckConstraint(
                condition=models.Q(unit_price__gte=0), name='storefront_item_price_nonneg',
            ),
            models.CheckConstraint(
                condition=models.Q(line_total__gte=0), name='storefront_item_total_nonneg',
            ),
        ]

    def clean(self):
        errors = {}
        if self.order_id and self.product_id:
            if self.product.business_id != self.order.storefront.business_id:
                errors['product'] = 'The product must belong to the order business.'
        if self.quantity is not None and self.unit_price is not None:
            if self.line_total != self.quantity * self.unit_price:
                errors['line_total'] = 'Line total must equal quantity multiplied by unit price.'
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.product_name

class StorefrontActivity(models.Model):
    class EventType(models.TextChoices):
        SHOP_VISIT = 'shop_visit', 'Shop visit'
        PRODUCT_VIEW = 'product_view', 'Product view'
        PRODUCT_SEARCH = 'product_search', 'Product search'
        CART_ADD = 'cart_add', 'Add to cart'
        RECOMMENDATION_SHOWN = 'recommendation_shown', 'Recommendation shown'
        RECOMMENDATION_CLICK = 'recommendation_click', 'Recommendation clicked'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    storefront = models.ForeignKey(
        Storefront, on_delete=models.CASCADE, related_name='activity_events',
    )
    event_id = models.UUIDField()
    session_id = models.UUIDField()
    event_type = models.CharField(max_length=32, choices=EventType.choices)
    listing = models.ForeignKey(
        StorefrontListing, on_delete=models.SET_NULL,
        related_name='activity_events', blank=True, null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at',)
        constraints = [
            models.UniqueConstraint(
                fields=('storefront', 'event_id'),
                name='uniq_storefront_activity_event',
            ),
        ]
        indexes = [
            models.Index(fields=('storefront', 'event_type', 'created_at')),
            models.Index(fields=('listing', 'event_type', 'created_at')),
            models.Index(fields=('storefront', 'session_id', 'created_at')),
        ]

    def clean(self):
        if self.listing_id and self.storefront_id:
            if self.listing.storefront_id != self.storefront_id:
                raise ValidationError({
                    'listing': 'The listing must belong to this storefront.',
                })

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
