import time

from django.core.management.base import BaseCommand

from intelligence.services.automation import process_due_automations


class Command(BaseCommand):
    help = (
        "Process due StockFlow Intelligence automations. "
        "Use --loop for a persistent lightweight worker."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--loop",
            action="store_true",
            help="Keep processing due rules until interrupted.",
        )
        parser.add_argument(
            "--interval",
            type=int,
            default=60,
            help="Seconds between checks when --loop is enabled.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=50,
            help="Maximum due rules processed per pass.",
        )

    def handle(self, *args, **options):
        interval = max(10, int(options["interval"]))
        limit = max(1, min(int(options["limit"]), 500))

        while True:
            result = process_due_automations(limit=limit)
            self.stdout.write(
                self.style.SUCCESS(
                    "Automation pass: "
                    f"{result['processed']} processed, "
                    f"{result['completed']} completed, "
                    f"{result['failed']} failed."
                )
            )

            if not options["loop"]:
                return

            try:
                time.sleep(interval)
            except KeyboardInterrupt:
                self.stdout.write(
                    self.style.WARNING(
                        "StockFlow Intelligence automation worker stopped."
                    )
                )
                return
