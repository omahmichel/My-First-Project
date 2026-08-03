from django.core.management.base import BaseCommand, CommandError

from sales.mobile_money_service import (
    cleanup_expired_mobile_money_reservations,
)


class Command(BaseCommand):
    # Reconciles expired Paystack Mobile Money stock reservations.

    help = (
        "Verify expired Mobile Money sales with Paystack, finalize "
        "successful charges, and release stale reservations."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=100,
            help="Maximum expired reservations to process in one run.",
        )

    def handle(self, *args, **options):
        limit = options["limit"]

        if limit < 1:
            raise CommandError("--limit must be greater than zero.")

        summary = cleanup_expired_mobile_money_reservations(
            batch_size=limit,
        )
        message = (
            "Mobile Money reservation cleanup complete: "
            f"scanned={summary['scanned']}, "
            f"finalized={summary['finalized']}, "
            f"released={summary['released']}, "
            f"deferred={summary['deferred']}, "
            f"skipped={summary['skipped']}."
        )

        if summary["deferred"]:
            self.stdout.write(self.style.WARNING(message))
        else:
            self.stdout.write(self.style.SUCCESS(message))
