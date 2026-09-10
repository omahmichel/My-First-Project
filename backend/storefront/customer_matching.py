import re
from businesses.models import Business
from customers.models import Customer
from rest_framework.exceptions import ValidationError


def normalized_phone(value):
    digits = re.sub(r'[^0-9]', '', str(value))
    if digits.startswith('00'):
        digits = digits[2:]
    if len(digits) == 10 and digits.startswith('0'):
        digits = '233' + digits[1:]
    return digits


def resolve_order_customer(*, order, user):
    business_id = order.storefront.business_id
    Business.objects.select_for_update().get(pk=business_id)
    phone = normalized_phone(order.customer_phone)
    if not phone:
        raise ValidationError({'customer': 'The order needs a valid buyer phone number.'})
    matches = [row for row in Customer.objects.filter(business_id=business_id).order_by('id') if normalized_phone(row.phone) == phone]
    if len(matches) > 1:
        raise ValidationError({'customer': 'Multiple customer accounts use this phone number. Review the customer records before completing this order.'})
    if matches:
        customer = matches[0]
        same_name = ' '.join(customer.name.split()).casefold() == ' '.join(order.customer_name.split()).casefold()
        if not customer.is_active or not same_name:
            raise ValidationError({'customer': 'This phone belongs to an inactive account or a different customer name. Review the buyer details before completion.'})
        return customer
    return Customer.objects.create(business_id=business_id, name=order.customer_name, phone=order.customer_phone, created_by=user)
