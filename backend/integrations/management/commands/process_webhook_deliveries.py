from django.core.management.base import BaseCommand

from integrations.webhooks.service import process_due_webhook_deliveries


class Command(BaseCommand):
    help = "Process queued StockFlow outbound webhook deliveries."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=50)

    def handle(self, *args, **options):
        result = process_due_webhook_deliveries(
            limit=max(1, min(int(options["limit"]), 200))
        )
        self.stdout.write(self.style.SUCCESS(
            "Webhook delivery processing complete: "
            f"processed={result['processed']} sent={result['sent']} "
            f"failed={result['failed']}"
        ))
