"""Server-owned GHS charges. Historical records retain their stored fee."""
from decimal import Decimal, ROUND_HALF_UP

SUBSCRIPTION_FEE_PERCENT = Decimal("2.50")
CUSTOMER_FEE_PERCENT = Decimal("1.30")

def payment_fee(amount, percent):
    return (Decimal(amount) * percent / Decimal("100")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )

CUSTOMER_FEE_CAP = Decimal("20.00")

def customer_payment_fee(amount):
    """Cap new customer charges only; never reprice stored attempts."""
    return min(payment_fee(amount, CUSTOMER_FEE_PERCENT), CUSTOMER_FEE_CAP)
