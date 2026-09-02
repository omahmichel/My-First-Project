from django.core.management.base import BaseCommand

from sales.merchant_payout_service import process_merchant_payout
from sales.models import MerchantPayout


class Command(BaseCommand):
    help = "Process queued StockFlow merchant payouts through Paystack."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=50)

    def handle(self, *args, **options):
        limit = max(1, min(int(options["limit"]), 500))
        payout_ids = list(
            MerchantPayout.objects.filter(
                status__in=(
                    MerchantPayout.Status.PENDING,
                    MerchantPayout.Status.RETRY,
                    MerchantPayout.Status.BLOCKED,
                    MerchantPayout.Status.PROCESSING,
                )
            )
            .order_by("created_at")
            .values_list("id", flat=True)[:limit]
        )

        processed = 0
        successful = 0
        for payout_id in payout_ids:
            payout = process_merchant_payout(payout_id)
            processed += 1
            if payout.status == MerchantPayout.Status.SUCCESSFUL:
                successful += 1
            self.stdout.write(
                f"{payout.reference}: {payout.status} "
                f"({payout.amount} {payout.currency})"
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Merchant payout run complete: processed={processed}, "
                f"successful={successful}."
            )
        )
