from datetime import date

from django.core.management.base import BaseCommand, CommandError

from sales.debt_reminder_service import process_debt_reminders


class Command(BaseCommand):
    # Processes one bounded batch of audited 10-day debt reminders.

    help = (
        "Create and send due customer debt SMS reminders through mNotify."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=100,
            help="Maximum reminder schedules to process in one run.",
        )
        parser.add_argument(
            "--as-of-date",
            help=(
                "Optional processing date in YYYY-MM-DD format for "
                "controlled reconciliation."
            ),
        )

    def handle(self, *args, **options):
        limit = options["limit"]

        if limit < 1:
            raise CommandError("--limit must be greater than zero.")

        as_of_date = None
        raw_as_of_date = options.get("as_of_date")

        if raw_as_of_date:
            try:
                as_of_date = date.fromisoformat(raw_as_of_date)
            except ValueError as exc:
                raise CommandError(
                    "--as-of-date must use YYYY-MM-DD format."
                ) from exc

        summary = process_debt_reminders(
            as_of_date=as_of_date,
            batch_size=limit,
        )
        message = (
            "Debt reminder processing complete: "
            f"created={summary['created']}, "
            f"scanned={summary['scanned']}, "
            f"sent={summary['sent']}, "
            f"failed={summary['failed']}, "
            f"skipped={summary['skipped']}, "
            f"deferred={summary['deferred']}."
        )

        if summary["failed"]:
            self.stdout.write(self.style.WARNING(message))
        else:
            self.stdout.write(self.style.SUCCESS(message))
